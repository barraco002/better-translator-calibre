# Changelog

## v1.1.0 (2026-10-26)

- Fix queue deadlocks on worker cancellation and processing/caching failures;
  bound automatic concurrency to six and join executor threads before returning.
- Check cancellation during retry/cooldown waits and streaming, and stop sibling
  workers on shutdown. In-flight HTTP requests remain timeout-bound.
- Honor shared Retry-After cooldowns, including the final failed request.
- Detect stream EOF, malformed chunks, API errors, empty output and truncation.
  Retry the whole paragraph and close responses.
- Refuse batch export with failed paragraphs; restore Advanced Mode state on errors.
- Fix metrics double-counting and reset progress for repeated jobs.
- Isolate custom engines; default custom AI providers to non-streaming.
- Require verified TLS and retain HTTP exception chains for retry headers.
- Fix attribution/project links and expose the optional output-folder setting.
- Declare Calibre >= 6.0 to match Python 3.10 / Qt 6 usage.
- Add deterministic ZIP/checksums, isolated tests, local HTTP/EPUB integration,
  ZIP-loader smoke test, Windows CI and Spanish installation instructions.

## v1.0.0 (2026-10-24) — Better Translator

First fork release, based on Ebook Translator v2.4.2 by bookfere.com.

### Performance & robustness
- Shared translation thread pool with bounded `done_queue` (maxsize 64) and
  `await put()` backpressure.
- Retry backoff: exponential `min(5 x 2^(retry-1), 60)s` + random 0–2 s jitter.
- Global 429 throttle: +15 s cooldown guarded by a `Lock`, coordinated across
  all concurrent workers.
- Progress line with live metrics every 25 items (completed / pending / aborts).

### Features
- `open_folder_after_translate` config option: auto-open the folder of the
  finished ebook after each completed translation (advanced and batch mode).

### Packaging
- Rebranded to **Better Translator**: plugin identifier `better-translator`,
  import name `calibre_plugins.better_translator`, config store
  `plugins/better_translator`, User-Agent `Better-Translator/x.y.z`,
  independent translation cache and settings directory.
- Electric version (1.0.0); internal class name `EbookTranslator` retained
  for upstream code-path compatibility.
