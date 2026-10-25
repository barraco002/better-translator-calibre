import os

from calibre.constants import DEBUG  # type: ignore
from calibre.customize import InterfaceActionBase  # type: ignore
from calibre.utils.localization import _  # type: ignore


__license__ = 'GPL v3'
__copyright__ = '2023, bookfere.com'
# Better Translator fork: (c) 2026, barraco002
__docformat__ = 'restructuredtext en'

load_translations()  # type: ignore


# To prevent update errors, avoid importing anything from plugin modules.
def _z(message): return message


class EbookTranslator(InterfaceActionBase):
    """Development environment requirements for the project:
    - Calibre version: >= 5.0.0
    - Python version: >=3.8.5
    """
    name = _z('Better Translator')
    title = _(name)
    supported_platforms = ['windows', 'osx', 'linux']
    identifier = 'better-translator'
    author = 'bookfere.com (Better Translator) / barraco002 (Better Translator)'
    version = (1, 0, 0)
    __version__ = 'v' + '.'.join(map(str, version))
    description = _(
        'Fast ebook translation for Calibre with AI engines: parallel '
        'requests, adaptive backoff, live metrics and OpenAI-compatible '
        'providers. Enhanced fork of the acclaimed Better Translator.')
    # see: https://www.mobileread.com/forums/showthread.php?t=242223
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = 'calibre_plugins.better_translator.ui:EbookTranslatorGui'

    # The DEBUG constant cannot be shared with new worker processes.
    # To ensure that it is available, add it to the OS environment.
    if DEBUG:
        os.environ.update(CALIBRE_DEBUG=str(DEBUG))

    def is_customizable(self):
        return False
