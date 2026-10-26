# Contributing

Install [Calibre](https://calibre-ebook.com/download) first. It supplies the Python,
Qt and ebook libraries used by the plugin. No paid services or API keys are needed.
Run these commands from the repository root:

```text
calibre-debug --exec-file tools/run_tests.py
calibre-debug --exec-file tools/build_plugin.py
calibre-debug --exec-file tools/smoke_plugin.py
```

On Windows, if Calibre is not on PATH:

```powershell
& 'C:\Program Files\Calibre2\calibre-debug.exe' --exec-file tools/run_tests.py
```

The suite uses a temporary configuration/cache, a local HTTP server and a synthetic
EPUB. It does not need your normal library or real provider credentials.
Run one module with `calibre-debug --exec-file tools/run_tests.py -- tests.lib.test_reliability`.

The builder puts the installable ZIP and SHA256SUMS.txt in `dist/`, using an explicit
runtime-file allowlist and fixed ZIP metadata. Never package a working directory
with its settings, caches, API keys or `.git` data. Do not upload private books.

For a fix, add a regression test that reproduces the failure. Retain upstream credit
and GPL v3 licensing. Report which Calibre/platform combinations you actually tested,
and distinguish local API fixtures from live-service validation.

References: [Calibre plugin development](https://manual.calibre-ebook.com/creating_plugins.html)
and [plugin API](https://manual.calibre-ebook.com/plugins.html).
