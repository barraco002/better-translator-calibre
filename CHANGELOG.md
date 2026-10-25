# Changelog

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
