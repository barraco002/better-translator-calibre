"""Real local HTTP and EPUB conversion. Uses no paid API or private book."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
from unittest.mock import patch

from ...engines.openai_compat import OpenAICompatTranslate
from ...lib.cache import TranslationCache
from ...lib.conversion import convert_book
from ...lib.element import ElementHandler
from ...lib.translation import Glossary, Translation


class TestLocalHTTPAndEPUB(unittest.TestCase):
    def test_real_http_request_translation_cache_and_epub_roundtrip(self):
        received = []
        class API(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path, body))
                text = body['messages'][-1]['content']
                translated = text.replace('Hello world', 'Hola mundo').replace('Test Book', 'Libro de prueba')
                response = json.dumps({'choices': [{'message': {'content': translated},
                                                   'finish_reason': 'stop'}]}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        server = ThreadingHTTPServer(('127.0.0.1', 0), API)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='better-translator-epub-') as directory:
                root = Path(directory)
                source, target = root / 'source.epub', root / 'translated.epub'
                with zipfile.ZipFile(source, 'w') as epub:
                    epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
                    epub.writestr('META-INF/container.xml',
                        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                        '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
                        '</rootfiles></container>')
                    epub.writestr('content.opf',
                        '<package version="2.0" unique-identifier="id" xmlns="http://www.idpf.org/2007/opf">'
                        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                        '<dc:identifier id="id">urn:uuid:better-translator-test</dc:identifier>'
                        '<dc:title>Test Book</dc:title><dc:creator>Test author</dc:creator><dc:language>en</dc:language>'
                        '</metadata><manifest><item id="page" href="chapter.xhtml" media-type="application/xhtml+xml"/>'
                        '</manifest><spine><itemref idref="page"/></spine></package>')
                    epub.writestr('chapter.xhtml',
                        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test Book</title></head>'
                        '<body><p>Hello world, <em>reader</em>.</p>'
                        '<p><a href="https://example.com">Hello world</a></p></body></html>')
                provider = type('LocalAPI', (OpenAICompatTranslate,), {})
                provider.set_engine_data({'name': 'Local test', 'model': 'test-model',
                    'endpoint': 'http://127.0.0.1:%s/v1/chat/completions' % server.server_port})
                provider.set_config({'api_keys': ['local-test-key'], 'stream': False,
                                     'concurrency_limit': 2, 'request_interval': 0})
                translator = provider()
                translator.set_source_lang('English')
                translator.set_target_lang('Spanish')
                translation = Translation(translator, Glossary(translator.placeholder))
                translation.set_batch(True)
                handler = ElementHandler(translator.placeholder, translator.separator, 'below')
                handler.load_remove_rules([])
                handler.load_reserve_rules([])
                with patch.multiple(TranslationCache, dir_path=str(root), cache_path=str(root / 'cache'),
                                    temp_path=str(root / 'temp')):
                    cache = TranslationCache('integration')
                    translation.set_callback(cache.update_paragraph)
                    try:
                        convert_book(str(source), str(target), translation, handler, cache,
                                     'Local HTTP integration test', 'utf-8', lambda *args: None)
                        self.assertGreater(len(cache.all_paragraphs()), 0)
                        self.assertTrue(all(p.translation for p in cache.all_paragraphs()))
                    finally:
                        cache.close()
                self.assertTrue(received)
                self.assertTrue(all(path == '/v1/chat/completions' for path, _ in received))
                with zipfile.ZipFile(target) as epub:
                    self.assertIsNone(epub.testzip())
                    xhtml = '\n'.join(epub.read(name).decode('utf-8') for name in epub.namelist()
                                      if name.endswith(('.xhtml', '.html')))
                    self.assertIn('Hola mundo', xhtml)
                    self.assertIn('Hello world', xhtml)
                    self.assertIn('https://example.com', xhtml)
                    self.assertIn('reader', xhtml)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
