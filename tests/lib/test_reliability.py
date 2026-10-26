"""Regression cases for failures found while reviewing the fork."""
import asyncio
import io
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ...engines.openai import ChatgptTranslate
from ...engines.openai_compat import OpenAICompatTranslate
from ...lib.cache import Paragraph
from ...lib.config import Configuration
from ...lib.exception import TranslationCanceled, TranslationFailed, UnexpectedResult
from ...lib.handler import Handler
from ...lib.translation import Glossary, ProgressBar, Translation, get_engine_class
from ...lib.utils import request


def paragraph(index):
    return Paragraph(index, str(index), '<p>Hello</p>', 'Hello')


def engine(**kwargs):
    values = dict(name='Test engine', max_error_count=0, request_attempt=1,
                  concurrency_limit=4, request_interval=0, merge_enabled=False,
                  translate=Mock(return_value='Hola'), match_error=lambda _: False,
                  get_target_lang=lambda: 'Spanish')
    values.update(kwargs)
    return SimpleNamespace(**values)


class TestHandlerReliability(unittest.IsolatedAsyncioTestCase):
    async def run_handler(self, handler):
        await asyncio.wait_for(handler.process_tasks(), timeout=3)

    async def test_slow_consumer_drains_more_than_queue_capacity(self):
        items = [paragraph(i) for i in range(250)]
        processed = []
        handler = Handler(items, 6, lambda p: setattr(p, 'translation', 'Hola'),
                          lambda p: processed.append(p.id), 0)
        await self.run_handler(handler)
        self.assertEqual(set(processed), set(range(250)))
        self.assertEqual(len(processed), 250)
        self.assertEqual(handler.stats, {'done': 250, 'errors': 0})
        self.assertEqual(handler.done_queue.qsize(), 0)

    async def test_cancel_one_worker_propagates_without_join_deadlock(self):
        def cancel(p):
            raise TranslationCanceled('cancel')
        handler = Handler([paragraph(i) for i in range(30)], 6, cancel, lambda p: None, 0)
        with self.assertRaises(TranslationCanceled):
            await self.run_handler(handler)

    async def test_processing_error_propagates_without_join_deadlock(self):
        def process(p):
            raise OSError('disk full')
        handler = Handler([paragraph(i) for i in range(200)], 6, lambda p: None, process, 0)
        with self.assertRaisesRegex(OSError, 'disk full'):
            await self.run_handler(handler)

    async def test_paragraph_error_is_delivered_and_remaining_work_finishes(self):
        processed = []
        def translate(p):
            if p.id == 3:
                raise ValueError('unavailable')
        handler = Handler([paragraph(i) for i in range(12)], 3, translate,
                          processed.append, 0)
        await self.run_handler(handler)
        self.assertEqual(len(processed), 12)
        self.assertEqual(handler.stats, {'done': 11, 'errors': 1})
        self.assertIn('unavailable', next(p for p in processed if p.id == 3).error)

    async def test_empty_handler_and_auto_concurrency_are_bounded(self):
        empty = Handler([], 0, lambda p: None, lambda p: None, 0)
        await self.run_handler(empty)
        auto = Handler([paragraph(i) for i in range(10000)], 0,
                       lambda p: None, lambda p: None, 0)
        self.assertEqual(auto.concurrency_limit, 6)

    async def test_executor_threads_are_joined(self):
        handler = Handler([paragraph(0)], 1, lambda p: None, lambda p: None, 0)
        await self.run_handler(handler)
        self.assertTrue(all(not thread.is_alive() for thread in handler.pool._threads))


class TestTranslationReliability(unittest.TestCase):
    def translation(self, **kwargs):
        return Translation(engine(**kwargs), Glossary(ChatgptTranslate.placeholder))

    def test_metrics_never_advance_progress_twice(self):
        translation = self.translation()
        translation.log = Mock()
        translation.handle([paragraph(i) for i in range(51)])
        self.assertEqual(translation.progress_bar._count, 51)
        self.assertEqual(translation.progress_bar.length, 1)
        self.assertIn('pending 26', next(
            call.args[0] for call in translation.log.call_args_list
            if call.args[0].startswith('Metrics: 25/')))

    def test_translation_instance_can_run_twice(self):
        translation = self.translation()
        translation.handle([paragraph(0), paragraph(1)])
        translation.handle([paragraph(2)])
        self.assertEqual(translation.total, 1)
        self.assertEqual(translation.progress_bar._count, 1)
        self.assertEqual(translation.progress_bar.length, 1)

    def test_canceled_job_never_reports_completion(self):
        translation = self.translation()
        translation.cancel_request = lambda: True
        translation.progress = Mock()
        translation.handle([paragraph(0)])
        translation.progress.assert_not_called()

    def test_batch_refuses_partial_output(self):
        translation = self.translation(translate=Mock(side_effect=ValueError('network')),
                                       request_attempt=0)
        translation.batch = True
        with self.assertRaisesRegex(Exception, 'Translation failed'):
            translation.handle([paragraph(0)])

    def test_batch_cancellation_is_propagated(self):
        translation = self.translation()
        translation.batch = True
        translation.cancel_request = lambda: True
        with self.assertRaises(TranslationCanceled):
            translation.handle([paragraph(0)])

    def test_backoff_is_cancelable(self):
        translation = self.translation()
        canceled = threading.Event()
        translation.cancel_request = canceled.is_set
        with patch('calibre_plugins.better_translator.lib.translation.time.sleep',
                   side_effect=lambda _: canceled.set()) as sleep:
            with self.assertRaises(TranslationCanceled):
                translation._sleep(60)
        sleep.assert_called_once()

    def test_throttle_is_cancelable(self):
        translation = self.translation()
        import time
        translation.throttle_until = time.monotonic() + 60
        translation.cancel_request = lambda: True
        with self.assertRaises(TranslationCanceled):
            translation._throttle_wait()

    def test_retry_after_is_shared_even_on_last_attempt(self):
        error = RuntimeError('HTTP 429 Too Many Requests')
        error.headers = {'Retry-After': '42'}
        translation = self.translation(translate=Mock(side_effect=error), request_attempt=0)
        with patch('calibre_plugins.better_translator.lib.translation.time.monotonic', return_value=100):
            with self.assertRaises(TranslationFailed):
                translation.translate_text(0, 'Hello')
        self.assertEqual(translation.throttle_until, 142)

    def test_retry_waits_for_shared_throttle(self):
        translation = self.translation(translate=Mock(side_effect=[RuntimeError('429'), 'Hola']))
        with patch.object(translation, '_sleep'), patch.object(translation, '_throttle_wait') as wait:
            self.assertEqual(translation.translate_text(0, 'Hello'), 'Hola')
        self.assertEqual(wait.call_count, 2)

    def test_retry_after_wrapped_http_date_and_bad_values(self):
        inner = RuntimeError('429')
        outer = RuntimeError('wrapped')
        outer.__cause__ = inner
        inner.headers = {'Retry-After': 'Thu, 01 Jan 1970 00:02:00 GMT'}
        with patch('calibre_plugins.better_translator.lib.translation.time.time', return_value=100):
            self.assertEqual(Translation._retry_after(outer), 20)
        for value in ('garbage', 'inf', 'NaN'):
            inner.headers['Retry-After'] = value
            self.assertIsNone(Translation._retry_after(outer))

    def test_stream_failure_retries_whole_paragraph(self):
        def broken():
            yield 'Partial'
            raise UnexpectedResult('EOF')
        def complete():
            yield 'Hola'
        translation = self.translation(translate=Mock(side_effect=[broken(), complete()]))
        item = paragraph(0)
        with patch.object(translation, '_sleep'):
            translation.translate_paragraph(item)
        self.assertEqual(item.translation, 'Hola')
        self.assertEqual(translation.translator.translate.call_count, 2)

    def test_stream_cancel_closes_generator(self):
        closed = []
        def source():
            try:
                yield 'first'
                yield 'second'
            finally:
                closed.append(True)
        translation = self.translation(translate=lambda _: source())
        translation.total = 1
        canceled = threading.Event()
        translation.cancel_request = canceled.is_set
        translation.streaming = lambda text: canceled.set() if text == 'first' else None
        with self.assertRaises(TranslationCanceled):
            translation.translate_text(0, 'Hello')
        self.assertEqual(closed, [True])

    def test_empty_translation_is_not_cached_as_success(self):
        translation = self.translation(translate=lambda _: '  ', request_attempt=0)
        item = paragraph(0)
        with self.assertRaises(TranslationFailed):
            translation.translate_paragraph(item)
        self.assertIsNone(item.translation)

    def test_progress_load_resets_and_handles_empty_input(self):
        progress = ProgressBar()
        progress.load(1)
        self.assertEqual(progress.count, 1)
        progress.load(2)
        self.assertEqual(progress.count, 1)
        self.assertEqual(progress.length, .5)
        progress.load(0)
        self.assertEqual(progress.length, 0)


class TestOpenAIResponseReliability(unittest.TestCase):
    def setUp(self):
        self.translator = ChatgptTranslate()
        self.translator.stream = False

    def test_content_blocks_are_joined(self):
        data = {'choices': [{'message': {'content': [{'text': 'Hola '}, {'text': 'mundo'}]}}]}
        self.assertEqual(self.translator.get_result(json.dumps(data)), 'Hola mundo')

    def test_invalid_empty_or_truncated_responses_fail(self):
        for data in (None, [], {'choices': []}, {'error': {'message': 'quota'}},
                     {'choices': [{'message': {'content': None}}]},
                     {'choices': [{'message': {'content': 'partial'}, 'finish_reason': 'length'}]},
                     {'choices': [{'message': {'content': ''}, 'finish_reason': 'content_filter'}]}):
            with self.subTest(data=data), self.assertRaises(UnexpectedResult):
                self.translator.get_result(json.dumps(data))

    def read_stream(self, data):
        self.translator.stream = True
        response = io.BytesIO(data)
        try:
            return ''.join(self.translator.get_result(response))
        finally:
            self.assertTrue(response.closed)

    def test_sse_without_space_comments_and_usage(self):
        data = (b': ping\n\nevent: message\n'
                b'data:{"choices":[{"delta":{"content":"Hola"}}]}\n\n'
                b'data: {"choices":[],"usage":{}}\n\ndata:[DONE]\n')
        self.assertEqual(self.read_stream(data), 'Hola')

    def test_eof_without_done_fails_instead_of_spinning(self):
        with self.assertRaisesRegex(UnexpectedResult, 'ended unexpectedly'):
            self.read_stream(b'data:{"choices":[{"delta":{"content":"Partial"}}]}\n')

    def test_finish_stop_allows_clean_eof(self):
        self.assertEqual(self.read_stream(
            b'data:{"choices":[{"delta":{"content":"Hola"},"finish_reason":"stop"}]}\n'), 'Hola')

    def test_invalid_json_fails_instead_of_dropping_text(self):
        with self.assertRaises(UnexpectedResult):
            self.read_stream(b'data: broken json\n')

    def test_stream_reports_errors_and_truncation(self):
        for data in (b'data:{"error":{"message":"rate limit"}}\n',
                     b'data:{"choices":[{"delta":{},"finish_reason":"length"}]}\n'):
            with self.subTest(data=data), self.assertRaises(UnexpectedResult):
                self.read_stream(data)


class TestProviderIsolation(unittest.TestCase):
    def test_configuration_instances_do_not_share_values(self):
        first, second = Configuration(), Configuration()
        first.set('translate_engine', 'alpha')
        self.assertIsNone(second.get('translate_engine'))

    def test_tls_failure_does_not_disable_certificate_checks(self):
        with patch('calibre_plugins.better_translator.lib.utils.ssl') as tls, \
                patch('calibre_plugins.better_translator.lib.utils.Browser') as browser:
            tls.create_default_context.side_effect = OSError('no certificates')
            with self.assertRaisesRegex(RuntimeError, 'TLS certificate verification'):
                request('https://example.com')
            tls._create_unverified_context.assert_not_called()
            browser().open.assert_not_called()

    def test_existing_engine_does_not_change_when_another_is_selected(self):
        config = Configuration({'custom_ai_engines': {
            'alpha': {'endpoint': 'https://alpha.example/v1/chat/completions'},
            'beta': {'endpoint': 'https://beta.example/v1/chat/completions'},
        }, 'engine_preferences': {'alpha': {'model': 'model-a'}, 'beta': {'model': 'model-b'}}})
        with patch('calibre_plugins.better_translator.lib.translation.get_config', return_value=config):
            alpha = get_engine_class('alpha')
            beta = get_engine_class('beta')
        self.assertIsNot(alpha, beta)
        self.assertEqual(alpha().model, 'model-a')
        self.assertEqual(alpha.name, 'alpha')
        self.assertEqual(beta.name, 'beta')
        self.assertEqual(alpha.endpoint, 'https://alpha.example/v1/chat/completions')
        self.assertEqual(OpenAICompatTranslate.name, 'OpenAI-compatible')
        self.assertFalse(alpha().stream)
