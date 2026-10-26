# Validation for 1.1.0

Local environment: Windows, Calibre 9.16.0. Commands run from the repository root:

```text
calibre-debug --exec-file tools/run_tests.py
calibre-debug --exec-file tools/build_plugin.py
calibre-debug --exec-file tools/smoke_plugin.py
```

The suite covers inherited text/HTML extraction, alignment, metadata, cache,
configuration and engines, plus regressions for queue shutdown, processing failures,
shared cooldowns, cancellation, progress, streaming, provider isolation and TLS.
The integration test sends real HTTP to 127.0.0.1, processes a synthetic EPUB with
Calibre's conversion pipeline and checks original/translated text and link preservation.

The smoke test uses Calibre's actual ZIP loader, imports the GUI/settings from the
ZIP and constructs the footer with Qt. Consecutive builds should have the same
SHA-256: timestamps and text line endings are normalized.

Windows CI repeats the suite/build/smoke test on Calibre 6.0.0 and 9.16.0.
See the [actual results](https://github.com/barraco002/better-translator-calibre/actions/workflows/ci.yml).
Checks prove their covered cases; they do not prove perfect translation or universal
provider compatibility.

Not validated: Linux/macOS GUI, every historical Calibre release, live paid providers,
all network/proxy combinations and literary translation quality. Requests already
in flight remain subject to the configured timeout.
