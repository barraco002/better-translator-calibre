"""Load the built ZIP with Calibre's real plugin loader, in isolation."""
import os
from pathlib import Path
import sys
import tempfile


def main():
    from calibre.customize.zipplugin import loader
    from calibre.constants import __version__
    root = Path(__file__).resolve().parents[1]
    archive = Path(sys.argv[-1]) if sys.argv[-1].endswith('.zip') else next((root / 'dist').glob('*.zip'))
    plugin_class = loader.load(str(archive))
    plugin = plugin_class(str(archive))
    assert plugin.name == 'Better Translator'
    assert plugin.version == (1, 1, 0)
    from calibre_plugins.better_translator.ui import EbookTranslatorGui
    from calibre_plugins.better_translator.setting import TranslationSetting
    from calibre_plugins.better_translator.components.footer import Footer
    from qt.core import QApplication
    app = QApplication.instance() or QApplication([])
    app.is_dark_theme = False
    footer = Footer()
    links = footer.findChildren(type(footer.status))[1].text()
    assert 'https://github.com/barraco002/better-translator-calibre' in links
    assert 'https://bookfere.com' in links
    assert EbookTranslatorGui.name == plugin.name
    print('PASS: ZIP loaded, GUI/settings/footer imported and footer constructed; Calibre %s; plugin %s' % (
        __version__, plugin.version))
    footer.close()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='better-translator-smoke-') as config:
        os.environ['CALIBRE_CONFIG_DIRECTORY'] = config
        os.environ['LOCALAPPDATA'] = config
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        main()
