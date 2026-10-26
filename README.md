# Better Translator for Calibre

[Español](README.es.md) · [简体中文](README.zh-CN.md) · [Download](https://github.com/barraco002/better-translator-calibre/releases/latest)

Translate ebooks inside Calibre, keeping the original alongside the translation
or exporting translated text only. Better Translator is a GPL v3 fork of
[Ebook Translator v2.4.2](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)
by **bookfere.com**.

## Install

1. Download **Better-Translator-v1.1.0.zip** from the
   [latest release](https://github.com/barraco002/better-translator-calibre/releases/latest).
2. In Calibre, open **Preferences → Plugins → Load plugin from file** and select
   that ZIP. Keep it zipped; GitHub's automatic “Source code” ZIP is not the plugin.
3. Restart Calibre. Add **Translate Book** under **Preferences → Toolbars & menus**
   if the action is not visible.
4. Open the plugin's **Setting** menu, choose an engine, enter its API key if
   required, and select a target language. Try a short book in **Advanced Mode**.

Requires **Calibre 6.0 or newer** (Python 3.10 / Qt 6). Local validation uses Windows
and Calibre 9.16. CI checks Calibre 6.0.0 and 9.16.0. Other operating systems and
live paid providers have not been validated for this release.

## What changed in 1.1.0

- **Reliable worker lifecycle.** One shared request pool, a completion queue capped
  at 64 items, automatic concurrency capped at six, and joined threads on exit.
  A failing cache callback or canceled worker cannot leave queue joins hanging.
- **Cancelable backoff.** Exponential delays with jitter; rate limits coordinate
  workers within a translation job and honor `Retry-After` when available.
  Cancellation is checked during waits and between streaming chunks. An HTTP
  request already in flight can still take up to its configured timeout.
- **No silent partial translation.** Interrupted streams, malformed chunks, empty
  output and API truncation are failures. A stream retry starts the paragraph
  again; partial text is not cached as a completed translation. Batch mode refuses
  to export a job with failed paragraphs.
- **Accurate progress.** Metrics no longer increment the paragraph counter. Reusing
  a translation job resets its progress correctly.
- **Independent custom providers.** Selecting another OpenAI-compatible provider
  cannot overwrite a previously selected provider's definition or preferences.
  These providers default to non-streaming; concurrency/timeouts are configurable.
- **Verified packaging.** Deterministic ZIP, SHA-256 checksum, executable regression
  tests, local HTTP/EPUB integration, and a real Calibre ZIP-loader smoke test.
  See [validation](docs/VALIDATION.md).

Upstream features remain: advanced editing, batch mode, translation cache,
glossaries, custom engines, and Google / DeepL / ChatGPT / Gemini / Claude /
DeepSeek engines. Availability depends on the selected provider and model.

## Settings and privacy

The fork uses `plugins/better_translator` for configuration and `better-translator`
for plugin data. It can coexist with Ebook Translator; upstream settings and keys
are not imported automatically. Configure the fork separately.

The selected translation provider receives the paragraphs you ask it to translate.
API keys and cached text are stored locally by Calibre/the plugin; configuration
files are not a credential vault. Share sanitized logs only. HTTPS certificate
verification is required and is never disabled as a fallback.

**Open output folder after translation** is an opt-in setting. Its default is off.

## Troubleshooting and contributing

Check your endpoint, model ID, API key and quota if a provider rejects a request.
Lower concurrency for rate limits; adjust the timeout for slow models. Use Advanced
Mode to inspect and retry failed paragraphs. Machine translation still requires
human review for meaning, terminology and formatting.

[Report a bug](https://github.com/barraco002/better-translator-calibre/issues/new/choose)
with plugin/Calibre versions, OS and sanitized errors.
See [CONTRIBUTING](CONTRIBUTING.md) for test/build commands.

## Credits and license

Original Ebook Translator: **bookfere.com**. Better Translator fork: **barraco002**.
Licensed under [GNU GPL v3](LICENSE). Upstream authorship and licensing are retained.
