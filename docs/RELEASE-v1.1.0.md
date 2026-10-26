# Better Translator v1.1.0

Fixes cases where canceled workers, failed cache callbacks or cut-off streaming
responses could leave ebook translation stuck or incomplete.

- Clean worker shutdown; bounded automatic concurrency and completion queue.
- Cancelable retry waits, shared `Retry-After` cooldowns and whole-paragraph retries.
- Rejection of empty/truncated results and batch exports with failed paragraphs.
- Correct progress counters and independent custom provider configurations.
- Verified TLS, corrected links and an output-folder toggle in Settings.
- Reproducible ZIP, SHA-256 checksum, regression suite and local HTTP/EPUB integration.

Download **Better-Translator-v1.1.0.zip**, then in Calibre choose
**Preferences → Plugins → Load plugin from file**, select the ZIP and restart.
Calibre 6.0 or newer is required. GitHub's automatic source ZIP is not the plugin.

Local validation: Windows / Calibre 9.16.0. CI checks Calibre 6.0.0 and 9.16.0.
Paid APIs and Linux/macOS were not tested for this release. Canceling an in-flight
HTTP request may still wait for its timeout.

GPL v3. Fork by barraco002, based on Ebook Translator v2.4.2 by bookfere.com.
[Español](https://github.com/barraco002/better-translator-calibre/blob/main/README.es.md)
· [Validation](https://github.com/barraco002/better-translator-calibre/blob/main/docs/VALIDATION.md)
