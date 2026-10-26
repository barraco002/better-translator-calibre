"""Run the suite with calibre-debug --exec-file tools/run_tests.py.

Uses Calibre's Python/Qt/lxml runtime and an isolated configuration directory.
No API key or network service is required.
"""
import builtins
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='better-translator-tests-') as config:
        os.environ['CALIBRE_CONFIG_DIRECTORY'] = config
        os.environ['CALIBRE_OVERRIDE_LANG'] = 'en'
        os.environ['LOCALAPPDATA'] = config
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        builtins.load_translations = lambda: None
        from calibre.utils.localization import set_translators
        set_translators()
        import calibre_plugins
        name = 'calibre_plugins.better_translator'
        spec = importlib.util.spec_from_file_location(
            name, root / '__init__.py', submodule_search_locations=[str(root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        setattr(calibre_plugins, 'better_translator', package)
        spec.loader.exec_module(package)
        from qt.core import QApplication
        app = QApplication.instance() or QApplication([])
        app.is_dark_theme = False
        names = sys.argv[1:]
        if names and names[0] == '--':
            names.pop(0)
        if names:
            suite = unittest.defaultTestLoader.loadTestsFromNames([
                name + '.' + item for item in names])
        else:
            suite = unittest.defaultTestLoader.loadTestsFromNames([
                name + '.' + '.'.join(path.relative_to(root).with_suffix('').parts)
                for path in sorted((root / 'tests').rglob('test_*.py'))])
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__ == '__main__':
    raise SystemExit(main())
