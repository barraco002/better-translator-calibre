# Better Translator for Calibre

**Better Translator** is an enhanced fork of the acclaimed
[Ebook Translator](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)
(v2.4.2) by bookfere.com — a Calibre plugin that translates ebooks into any
language, keeping the original text or replacing it.

This fork keeps upstream's full feature set and adds a performance / robustness
layer for heavy batch translations against OpenAI-compatible APIs.

## What this fork adds (v1.0.0)

- **Shared parallel request pool** — translation workers are reused across
  requests with a bounded completion queue and backpressure, instead of one
  throwaway pool per request.
- **Exponential backoff with jitter** — retries wait `min(5 x 2^n, 60)s`
  plus up to 2 s of random jitter, instead of a fixed delay.
- **Coordinated 429 handling** — a 429 response applies a +15 s global
  throttle (thread-safe, shared lock) so concurrent workers back off together.
- **Live metrics** — every 25 items the worker prints
  `Metrics: N/M items | pending X | aborts Y`.
- **Auto-open the output folder** — when a translation finishes, the folder
  containing the produced ebook opens automatically
  (config key `open_folder_after_translate`, `true` by default in the
  packaged build).
- **Tuned defaults for OpenAI-compatible providers** — concurrency 6,
  request interval 0 s, 120 s timeout, streaming off; validated with
  DeepSeek V4.1 Flash (~56 tok/s, no wasted reasoning tokens).

## Installation

1. Download `Better-Translator-v1.0.0.zip` from
   [Releases](https://github.com/barraco002/better-translator-calibre/releases).
2. In Calibre: *Preferences -> Plugins -> Load plugin from file*.
3. Pick the zip and restart Calibre.

> Note: this is a separate plugin (identifier `better-translator`, config
> store `plugins/better_translator`). It does not conflict with an existing
> Ebook Translator installation.

## Compatibility

- Calibre >= 5.0 (upstream requirement), Python >= 3.8.5.
- All upstream engines remain available. The internal plugin class name is
  still `EbookTranslator` for compatibility with upstream code paths.

## Credits

- [bookfere.com](https://bookfere.com) — original **Ebook Translator** (GPL v3).
- **barraco002** — performance layer, rebrand and fork packaging.

Licensed under [GPL v3](LICENSE), inherited from upstream.
