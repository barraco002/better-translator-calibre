import re
import time
import json
import random
import threading
import math
from email.utils import parsedate_to_datetime
from types import GeneratorType

from calibre.utils.localization import _  # type: ignore

from ..engines import builtin_engines
from ..engines import GoogleFreeTranslateNew
from ..engines.base import Base
from ..engines.custom import CustomTranslate
from ..engines.openai_compat import OpenAICompatTranslate

from .utils import log, sep, trim, dummy, traceback_error
from .config import get_config
from .exception import TranslationFailed, TranslationCanceled
from .handler import Handler


load_translations()  # type: ignore


class Glossary:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.glossary = []

    def load_from_file(self, path):
        content = None
        try:
            with open(path, 'r', newline=None) as f:
                content = f.read().strip()
        except Exception:
            pass
        if not content:
            return
        groups = re.split(r'\n{2,}', content.strip(u'\ufeff'))
        for group in filter(trim, groups):
            group = group.split('\n')
            self.glossary.append(
                (group[0], group[0] if len(group) < 2 else group[1]))

    def replace(self, content):
        for wid, words in enumerate(self.glossary):
            replacement = self.placeholder[0].format(format(wid, '06'))
            content = content.replace(words[0], replacement)
        return content

    def restore(self, content):
        for wid, words in enumerate(self.glossary):
            pattern = self.placeholder[1].format(format(wid, '06'))
            # Eliminate the impact of backslashes on substitution.
            content = re.sub(pattern, lambda _: words[1], content)
        return content


class ProgressBar:
    total = 0
    length = 0.0
    step = 0

    _count = 0

    def load(self, total):
        self._count = 0
        self.length = 0.0
        self.total = total
        self.step = 1.0 / total if total else 0.0

    @property
    def count(self):
        self._count += 1
        self.length = min(1.0, self._count * self.step)
        return self._count


class Translation:
    def __init__(self, translator, glossary):
        self.translator = translator
        self.glossary = glossary

        self.fresh = False
        self.batch = False
        self.progress = dummy
        self.log = dummy
        self.streaming = dummy
        self.callback = dummy
        self.cancel_request = dummy

        self.total = 0
        self.progress_bar = ProgressBar()
        self.abort_count = 0
        # Adaptive throttle (level 3): when a 429/rate-limit error is seen,
        # every worker sleeps until this timestamp before issuing the next
        # request. Guarded by a lock because workers run in threads.
        self.throttle_lock = threading.Lock()
        self.throttle_until = 0.0
        self.state_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.metric_counter = 0

    def set_fresh(self, fresh):
        self.fresh = fresh

    def set_batch(self, batch):
        self.batch = batch

    def set_progress(self, progress):
        self.progress = progress

    def set_logging(self, log):
        self.log = log

    def set_streaming(self, streaming):
        self.streaming = streaming

    def set_callback(self, callback):
        self.callback = callback

    def set_cancel_request(self, cancel_request):
        self.cancel_request = cancel_request

    def need_stop(self):
        # Cancel the request if there are more than max continuous errors.
        with self.state_lock:
            return self.translator.max_error_count > 0 and \
                self.abort_count >= self.translator.max_error_count

    def _check_cancel(self):
        if self.cancel_request() or self.stop_event.is_set() or self.need_stop():
            raise TranslationCanceled(_('Translation canceled.'))

    def _sleep(self, seconds):
        # Poll cancellation during backoff instead of freezing for a minute.
        while seconds > 0:
            self._check_cancel()
            step = min(seconds, 0.1)
            time.sleep(step)
            seconds -= step

    def _throttle_wait(self):
        if not self.throttle_until:
            return
        while True:
            with self.throttle_lock:
                wait = self.throttle_until - time.monotonic()
            if wait <= 0:
                return
            self._sleep(min(wait, 0.5))

    @staticmethod
    def _retry_after(error):
        # Base.translate wraps HTTP errors; keep their Retry-After header useful.
        for _ in range(5):
            headers = getattr(error, 'headers', None)
            value = headers.get('Retry-After') if headers else None
            if value:
                try:
                    delay = float(value)
                except (ValueError, TypeError):
                    try:
                        delay = parsedate_to_datetime(value).timestamp() - time.time()
                    except (ValueError, TypeError, OverflowError):
                        return None
                return max(0, delay) if math.isfinite(delay) else None
            error = error.__cause__ or error.__context__
            if error is None:
                break
        return None

    def _consume_stream(self, translation):
        parts = []
        if self.total == 1:
            self.streaming('')
        try:
            for part in translation:
                self._check_cancel()
                if self.total == 1:
                    self.streaming(part)
                parts.append(part)
        finally:
            translation.close()
        return ''.join(parts)

    def translate_text(self, row, text, retry=0, interval=0):
        """Translation engine service error code documentation:
        * https://cloud.google.com/apis/design/errors
        * https://www.deepl.com/docs-api/error-handling/
        * https://platform.openai.com/docs/guides/error-codes/api-errors
        """
        while True:
            self._check_cancel()
            self._throttle_wait()
            try:
                translation = self.translator.translate(text)
                if isinstance(translation, GeneratorType):
                    translation = self._consume_stream(translation)
                self._check_cancel()
                if isinstance(translation, str) and not translation.strip():
                    raise TranslationFailed(_('The engine returned an empty translation.'))
                with self.state_lock:
                    self.abort_count = 0
                return translation
            except TranslationCanceled:
                raise
            except Exception as e:
                if self.cancel_request() or self.need_stop():
                    raise TranslationCanceled(_('Translation canceled.'))
                with self.state_lock:
                    self.abort_count += 1
                error_text = str(e)
                low = error_text.lower()
                if '429' in error_text or 'rate limit' in low or \
                        'too many requests' in low:
                    cooldown = self._retry_after(e)
                    with self.throttle_lock:
                        self.throttle_until = max(
                            self.throttle_until,
                            time.monotonic() + (15 if cooldown is None else cooldown))
                if self.translator.match_error(error_text):
                    raise TranslationCanceled(_('Translation canceled.')) from e
                message = _('Failed to retrieve data from translate engine API.')
                if retry >= self.translator.request_attempt:
                    raise TranslationFailed('{}\n{}'.format(message, error_text)) from e
                retry += 1
                # Exponential backoff, capped at 60 s plus 0-2 s jitter.
                interval = min(5 * (2 ** min(retry - 1, 4)), 60)
                interval += random.uniform(0, 2)
                # Logging any errors that occur during translation.
                logged_text = text[:200] + '...' if len(text) > 200 else text
                error_messages = [
                    sep(), _('Original: {}').format(logged_text), sep('┈'),
                    _('Status: Failed {} times / Sleeping for {} seconds')
                    .format(retry, interval), sep('┈'), _('Error: {}')
                    .format(traceback_error())]
                if row >= 0:
                    error_messages.insert(1, _('Row: {}').format(row))
                self.log('\n'.join(error_messages), True)
                self._sleep(interval)

    def translate_paragraph(self, paragraph):
        if self.cancel_request():
            raise TranslationCanceled(_('Translation canceled.'))
        if paragraph.translation and not self.fresh:
            paragraph.is_cache = True
            return
        self.streaming('')
        self.streaming(_('Translating...'))
        text = self.glossary.replace(paragraph.original)
        translation = self.translate_text(paragraph.row, text)
        translation = self.glossary.restore(translation)
        paragraph.translation = translation.strip()
        # Apply aligment checking and processing.
        if self.translator.merge_enabled:
            paragraph.do_aligment(self.translator.separator)
        paragraph.engine_name = self.translator.name
        paragraph.target_lang = self.translator.get_target_lang()
        paragraph.is_cache = False

    def process_translation(self, paragraph):
        count = self.progress_bar.count
        self.progress(
            self.progress_bar.length, _('Translating: {}/{}').format(
                count, self.progress_bar.total))

        self.streaming(paragraph)
        self.callback(paragraph)

        row = paragraph.row
        original = paragraph.original.strip()
        if paragraph.error is None:
            self.log(sep())
            if row >= 0:
                self.log(_('Row: {}').format(row))
            self.log(_('Original: {}').format(original))
            self.log(sep('┈'))
            message = _('Translation: {}')
            if paragraph.is_cache:
                message = _('Translation (Cached): {}')
            self.log(message.format(paragraph.translation.strip()))
        # Live throughput metrics every 25 items (level 3).
        self.metric_counter += 1
        if self.metric_counter % 25 == 0 and self.total > 0:
            pending = max(0, self.total - count)
            self.log('Metrics: {}/{} items | pending {} | aborts {}'.format(
                self.metric_counter, self.total, pending, self.abort_count))

    def handle(self, paragraphs=None):
        start_time = time.time()
        paragraphs = list(paragraphs or [])
        self.total = 0
        self.abort_count = 0
        self.metric_counter = 0
        self.throttle_until = 0.0
        self.stop_event.clear()
        char_count = 0
        for paragraph in paragraphs:
            self.total += 1
            char_count += len(paragraph.original)

        self.log(sep())
        self.log(_('Start to translate ebook content'))
        self.log(sep('┈'))
        self.log(_('Item count: {}').format(self.total))
        self.log(_('Character count: {}').format(char_count))

        if self.total < 1:
            raise Exception(_('There is no content need to translate.'))
        self.progress_bar.load(self.total)

        handler = Handler(
            paragraphs, self.translator.concurrency_limit,
            self.translate_paragraph, self.process_translation,
            self.translator.request_interval, self.stop_event.set)
        try:
            handler.handle()
        except TranslationCanceled:
            self.log(_('Translation canceled.'), True)
            if self.batch:
                raise
            return

        self.log(sep())
        if self.batch and (self.need_stop() or handler.stats['errors']):
            raise Exception(_('Translation failed.'))
        consuming = round((time.time() - start_time) / 60, 2)
        self.log(_('Time consuming: {} minutes').format(consuming))
        self.log(_('Translation completed.'))
        self.progress(1, _('Translation completed.'))


def get_engine_class(engine_name=None):
    config = get_config()
    engine_name = engine_name or config.get('translate_engine')
    engines: dict[str, type[Base]] = {
        engine.name: engine for engine in builtin_engines
        if engine.name is not None}
    custom_engines = config.get('custom_engines') or {}
    custom_ai_engines = config.get('custom_ai_engines') or {}
    if engine_name in engines:
        engine_class = engines[engine_name]
    elif engine_name in custom_engines:
        engine_class = type('CustomProvider', (CustomTranslate,), {})
        engine_data = json.loads(custom_engines[engine_name])
        engine_class.set_engine_data(engine_data)
    elif engine_name in custom_ai_engines:
        engine_class = type('OpenAIProvider', (OpenAICompatTranslate,), {})
        engine_class.set_engine_data(dict(
            custom_ai_engines[engine_name], name=engine_name))
    else:
        engine_class = GoogleFreeTranslateNew
    engine_preferences = config.get('engine_preferences') or {}
    # Red de seguridad: si una definicion guardada llega sin 'name', las
    # preferencias siguen bajo la clave con la que el usuario conoce al motor.
    preferences = engine_preferences.get(engine_class.name)
    if preferences is None and engine_name is not None:
        preferences = engine_preferences.get(engine_name)
    engine_class.set_config(preferences or {})
    return engine_class


def get_translator(engine_class=None):
    config = get_config()
    engine_class = engine_class or get_engine_class()
    translator = engine_class()
    translator.set_search_paths(config.get('search_paths'))
    if config.get('proxy_enabled'):
        proxy_type: str | None = config.get('proxy_type')
        proxy_setting: dict[str, list] | None = config.get('proxy_setting')
        if proxy_type is not None and proxy_setting is not None:
            # Compatible with old proxy settings stored as a list.
            if isinstance(proxy_setting, list):
                proxy_setting = {'http': proxy_setting}
            host, port = proxy_setting.get(proxy_type) or ['', '']
            translator.set_proxy(proxy_type, host, port)
    translator.set_merge_enabled(config.get('merge_enabled'))
    return translator


def get_translation(translator, log=None):
    config = get_config()
    glossary = Glossary(translator.placeholder)
    if config.get('glossary_enabled'):
        glossary.load_from_file(config.get('glossary_path'))
    translation = Translation(translator, glossary)
    if get_config().get('log_translation'):
        translation.set_logging(log)
    return translation
