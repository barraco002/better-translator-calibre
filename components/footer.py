from qt.core import QWidget, QHBoxLayout, QLabel  # type: ignore


load_translations()  # type: ignore


class Footer(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.status = QLabel()

        github = 'https://github.com/barraco002/better-translator-calibre'
        link = QLabel(
            '<a href="{0}">Better Translator</a> ｜ '
            '<a href="{0}/issues">{1}</a> ｜ '
            'Based on <a href="https://bookfere.com">Ebook Translator</a>'
            .format(github, _('Feedback')))
        link.setStyleSheet('color:grey')
        link.setOpenExternalLinks(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.status)
        layout.addStretch(1)
        layout.addWidget(link)
