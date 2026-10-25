import json
import re
import time
import uuid
from types import GeneratorType

from qt.core import (  # type: ignore
    Qt, pyqtSignal, pyqtSlot, QDialog, QThread, QGridLayout, QPushButton,
    QPlainTextEdit, QObject, QTextCursor, QLabel, QComboBox, QLineEdit,
    QSpacerItem, QFileDialog)

from ..lib.utils import log, sorted_mixed_keys, traceback_error
from ..lib.config import get_config
from ..engines.custom import (
    create_engine_template, load_engine_data, CustomTranslate)
from ..engines.openai_compat import OpenAICompatTranslate
from ..engines import builtin_engines, GoogleFreeTranslateNew

from .lang import SourceLang, TargetLang
from .alert import AlertMessage
from .shortcut import set_shortcut


load_translations()  # type: ignore


class EngineList(QComboBox):
    def __init__(self, default=None):
        QComboBox.__init__(self)
        self.default = default
        self.wheelEvent = lambda event: None
        self.refresh()

    def layout(self):
        engines = sorted(builtin_engines, key=lambda item: not item.free)
        for engine in engines:
            previous_index = engines.index(engine) - 1
            if not engine.free and engines[previous_index].free:
                self.insertSeparator(previous_index + 1)
            self.addItem(_(engine.alias), engine.name)
        custom_engines = get_config().get('custom_engines') or {}
        if len(custom_engines) > 0:
            self.insertSeparator(len(builtin_engines) + 1)
        for name in sorted(custom_engines.keys(), key=sorted_mixed_keys):
            self.addItem(name, name)
        custom_ai_engines = get_config().get('custom_ai_engines') or {}
        if len(custom_ai_engines) > 0:
            self.insertSeparator(self.count())
        for name in sorted(custom_ai_engines.keys(), key=sorted_mixed_keys):
            data = custom_ai_engines.get(name) or {}
            self.addItem(data.get('alias') or name, name)
        if self.default:
            self.setCurrentIndex(self.findData(self.default))

    def refresh(self):
        self.clear()
        self.layout()


class EngineWorker(QObject):
    clear = pyqtSignal()
    translate = pyqtSignal(str)
    result = pyqtSignal(str)
    complete = pyqtSignal()
    check = pyqtSignal()
    usage = pyqtSignal(object)

    def __init__(self, translator):
        QObject.__init__(self)
        self.translator = translator
        self.translate.connect(self.translate_text)
        self.check.connect(self.check_usage)

    @pyqtSlot(str)
    def translate_text(self, text):
        self.clear.emit()
        self.result.emit(_('Translating...'))
        try:
            translation = self.translator.translate(text)
            if isinstance(translation, GeneratorType):
                clear = True
                for text in translation:
                    if clear:
                        self.clear.emit()
                        clear = False
                    self.result.emit(text)
                    time.sleep(0.05)
            else:
                self.clear.emit()
                self.result.emit(translation)
            self.complete.emit()
        except Exception:
            self.clear.emit()
            error_message = traceback_error()
            self.result.emit(error_message)
            log.error(error_message)

    @pyqtSlot()
    def check_usage(self):
        self.usage.emit(self.translator.get_usage())


class EngineTester(QDialog):
    usage_thread = QThread()
    translation_thread = QThread()

    def __init__(self, parent, translator):
        QDialog.__init__(self, parent)
        self.parent = parent
        self.translator = translator
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(_('Test Translation Engine'))
        self.setModal(True)
        self.setMinimumWidth(500)
        # self.setMaximumHeight(300)
        self.layout()
        self.show()

    def layout(self):
        layout = QGridLayout(self)

        source = QPlainTextEdit()
        source.setPlainText('Hello World!')
        cursor = source.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        source.setTextCursor(cursor)
        layout.addWidget(source, 0, 0, 1, 3)

        target = QPlainTextEdit()
        layout.addWidget(target, 1, 0, 1, 3)

        source_lang = SourceLang()
        source_lang.set_codes(
            self.translator.lang_codes.get('source'),
            not isinstance(self.translator, CustomTranslate))
        layout.addWidget(source_lang, 2, 0)

        def change_source_lang(lang):
            self.translator.set_source_lang(lang)
        change_source_lang(source_lang.currentText())
        source_lang.currentTextChanged.connect(change_source_lang)

        target_lang = TargetLang()
        target_lang.set_codes(
            self.translator.lang_codes.get('target'),
            self.parent.target_lang.currentText())
        layout.addWidget(target_lang, 2, 1)

        def change_target_lang(lang):
            self.translator.set_target_lang(lang)
        change_target_lang(target_lang.currentText())
        target_lang.currentTextChanged.connect(change_target_lang)

        translate = QPushButton(_('Translate'))
        layout.addWidget(translate, 2, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        usage = QLabel(_('Usage: checking...'))
        usage.setVisible(False)
        layout.addWidget(usage, 3, 0, 1, 3)

        self.usage_worker = EngineWorker(self.translator)
        self.usage_worker.moveToThread(self.usage_thread)
        self.usage_thread.finished.connect(self.usage_worker.deleteLater)
        self.usage_thread.start()

        def check_usage(text):
            if text is not None:
                usage.setText(_('Usage: {}').format(text))
                usage.setVisible(True)
            else:
                usage.setVisible(False)
        self.usage_worker.usage.connect(check_usage)
        self.usage_worker.check.emit()

        self.translate_worker = EngineWorker(self.translator)
        self.translate_worker.moveToThread(self.translation_thread)
        self.translation_thread.finished.connect(
            self.translate_worker.deleteLater)
        self.translation_thread.start()

        self.translate_worker.clear.connect(target.clear)
        self.translate_worker.result.connect(target.insertPlainText)
        self.translate_worker.complete.connect(self.usage_worker.check.emit)

        def test_translate():
            self.translate_worker.translate.emit(source.toPlainText())
        translate.clicked.connect(test_translate)

    def done(self, result):
        QDialog.done(self, result)
        self.usage_thread.quit()
        self.usage_thread.wait()
        self.translation_thread.quit()
        self.translation_thread.wait()


class ManageCustomEngine(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.parent = parent
        self.config = parent.config
        self.alert = AlertMessage(self)

        self.custom_engines = self.config.get('custom_engines').copy()
        self.engine_config = self.config.get('engine_preferences').copy()
        self.default_name = self.config.get('translate_engine')

        self.setWindowTitle(_('Custom Translation Engine'))
        self.setModal(True)
        self.setMinimumWidth(600)
        self.layout()

    def layout(self):
        layout = QGridLayout(self)
        custom_list = QComboBox()
        custom_add = QPushButton(_('Add'))
        custom_del = QPushButton(_('Delete'))
        custom_engine_data = QPlainTextEdit()
        custom_engine_data.setMinimumHeight(400)
        custom_clear = QPushButton(_('Clear'))
        custom_restore = QPushButton(_('Restore'))
        custom_verify = QPushButton(_('Verify'))
        custom_save = QPushButton(_('&Save'))
        layout.addWidget(custom_list, 0, 0, 1, 3)
        layout.addWidget(custom_add, 0, 3)
        layout.addWidget(custom_del, 0, 4)
        layout.addWidget(custom_engine_data, 1, 0, 1, 5)
        layout.addWidget(custom_clear, 2, 0)
        layout.addWidget(custom_restore, 2, 1)
        layout.addItem(QSpacerItem(0, 0), 2, 2)
        layout.addWidget(custom_verify, 2, 3)
        layout.addWidget(custom_save, 2, 4)
        layout.setColumnStretch(2, 1)

        def refresh_list():
            custom_list.clear()
            engines = sorted(self.custom_engines.keys(), key=sorted_mixed_keys)
            custom_list.addItems(engines)
        refresh_list()
        index = custom_list.findText(self.default_name)
        custom_list.setCurrentIndex(index if index != -1 else 0)

        def add_data():
            name = 'New Engine - %s' % uuid.uuid4().hex[:5]
            template = create_engine_template(name)
            custom_list.addItem(name)
            custom_list.setCurrentText(name)
            custom_engine_data.setPlainText(template)
            self.custom_engines[name] = template
        if len(self.custom_engines) < 1:
            add_data()

        def restore_data(name=None):
            name = name or custom_list.currentText()
            content = self.custom_engines.get(name)
            custom_engine_data.setPlainText(content)
        restore_data()

        def verify_data():
            valid, data = load_engine_data(custom_engine_data.toPlainText())
            if not valid:
                return self.alert.pop(data, 'warning')
            self.alert.pop(_('Valid engine data format.'))

        def save_data():
            current_name = custom_list.currentText()
            if not current_name:  # If all engine was deleted
                self.default_name = GoogleFreeTranslateNew.name
            else:
                # Validate the custom engine data
                raw_data = custom_engine_data.toPlainText()
                valid, data = load_engine_data(raw_data)
                if not valid:
                    return self.alert.pop(data, 'warning')
                # Check if the engine name exists
                new_name = data.get('name') or ''
                if new_name.lower() != current_name.lower():
                    exist_names = [
                        name.lower() for name in self.custom_engines]
                    if new_name.lower() in exist_names:
                        return self.alert.pop(
                            _('The engine name is already in use.'), 'warning')
                # Refresh custom engine data
                default_name = get_config().get('translate_engine')
                if self.default_name == current_name:
                    self.default_name = new_name
                    if current_name in self.engine_config:
                        data = self.engine_config.pop(current_name)
                        self.engine_config[new_name] = data
                if default_name == current_name:
                    default_name = new_name
                self.config.update(translate_engine=default_name)
                del self.custom_engines[current_name]
                self.custom_engines[new_name] = raw_data
                # Refresh the custom engine list
                refresh_list()
                custom_list.setCurrentText(new_name)
            # Update the custom engine
            self.config.update(custom_engines=self.custom_engines.copy())
            self.config.update(engine_preferences=self.engine_config.copy())
            self.config.commit()
            # Restore the selected engine
            self.config.update(translate_engine=self.default_name)
            self.alert.pop(_('The setting has been saved.'))

        def delete_data():
            current_index = custom_list.currentIndex()
            current_name = custom_list.itemText(current_index)
            if current_name in self.custom_engines:
                del self.custom_engines[current_name]
            if current_name in self.engine_config:
                del self.engine_config[current_name]
            if current_name == self.default_name:
                self.default_name = GoogleFreeTranslateNew.name
            custom_list.removeItem(current_index)

        def disable_save_button():
            disabled = custom_list.count() < 1
            custom_del.setDisabled(disabled)
            custom_clear.setDisabled(disabled)
            custom_restore.setDisabled(disabled)
            custom_verify.setDisabled(disabled)
        disable_save_button()

        custom_list.currentTextChanged.connect(disable_save_button)
        custom_list.currentTextChanged.connect(restore_data)
        custom_add.clicked.connect(add_data)
        custom_del.clicked.connect(delete_data)
        custom_clear.clicked.connect(custom_engine_data.clear)
        custom_restore.clicked.connect(restore_data)
        custom_verify.clicked.connect(verify_data)
        custom_save.clicked.connect(save_data)
        set_shortcut(custom_save, 'save', save_data, custom_save.text())

    def done(self, result):
        QDialog.done(self, result)
        self.parent.raise_()
        self.parent.activateWindow()


class ManageOpenAIEngine(QDialog):
    """Alta y gestion de APIs OpenAI-compatible (estilo "add provider").

    Formulario tipo harness: Provider ID (minusculas, sin espacios), Display
    name, Base URL (se normaliza a .../v1/chat/completions), API key y botón
    "Fetch modelos" que consulta <prefijo>/models en vivo. La definición se
    guarda en "custom_ai_engines" y la clave en "engine_preferences"
    [<provider id>].api_keys. El motor que las consume es
    engines.openai_compat.OpenAICompatTranslate.
    """

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.parent = parent
        self.config = parent.config
        self.alert = AlertMessage(self)
        self.current_id = ''

        self.custom_ai = self.config.get('custom_ai_engines').copy()
        self.engine_config = self.config.get('engine_preferences').copy()
        self.taken_names = [
            engine.name.lower() for engine in builtin_engines
            if engine.name is not None]
        self.taken_names += [
            name.lower()
            for name in self.config.get('custom_engines') or {}]

        self.setWindowTitle('API OpenAI-compatible')
        self.setModal(True)
        self.setMinimumWidth(650)
        self.layout()
        self.show()

    def layout(self):
        layout = QGridLayout(self)

        engine_list = QComboBox()
        engine_list.addItems(
            sorted(self.custom_ai.keys(), key=sorted_mixed_keys))
        engine_add = QPushButton('Agregar')
        engine_del = QPushButton('Borrar')
        layout.addWidget(engine_list, 0, 0, 1, 2)
        layout.addWidget(engine_add, 0, 2)
        layout.addWidget(engine_del, 0, 3)

        id_edit = QLineEdit()
        id_edit.setPlaceholderText('p. ej. radox (minusculas, sin espacios)')
        display_edit = QLineEdit()
        display_edit.setPlaceholderText('p. ej. Radox AI')
        url_edit = QLineEdit()
        url_edit.setPlaceholderText('https://api.host.com/v1')
        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText('se necesita para Fetch modelos')
        model_list = QComboBox()
        model_list.setEditable(True)
        fetch_models = QPushButton('Fetch modelos')
        save_engine = QPushButton('&Guardar')

        layout.addWidget(QLabel('Provider ID'), 1, 0)
        layout.addWidget(id_edit, 1, 1, 1, 3)
        layout.addWidget(QLabel('Display name'), 2, 0)
        layout.addWidget(display_edit, 2, 1, 1, 3)
        layout.addWidget(QLabel('Base URL'), 3, 0)
        layout.addWidget(url_edit, 3, 1, 1, 3)
        layout.addWidget(QLabel('Protocolo'), 4, 0)
        layout.addWidget(QLabel('OpenAI Chat Completions'), 4, 1)
        layout.addWidget(QLabel('API key'), 5, 0)
        layout.addWidget(key_edit, 5, 1)
        layout.addWidget(fetch_models, 5, 2)
        layout.addWidget(QLabel('Modelo'), 6, 0)
        layout.addWidget(model_list, 6, 1, 1, 3)
        probar_engine = QPushButton('Probar motor')
        exportar_engines = QPushButton('Exportar JSON')
        importar_engines = QPushButton('Importar JSON')
        layout.addWidget(probar_engine, 7, 0, 1, 3)
        layout.addWidget(save_engine, 7, 3)
        layout.addWidget(exportar_engines, 8, 2)
        layout.addWidget(importar_engines, 8, 3)
        layout.setColumnStretch(1, 1)

        def normalized_url():
            url = url_edit.text().strip().rstrip('/')
            if url and not url.endswith('/chat/completions'):
                url += '/chat/completions'
            return url

        def fetch_list():
            url = normalized_url()
            if not re.match(r'^https?://', url):
                return self.alert.pop(
                    'Escribe una Base URL valida (https://...).', 'warning')
            key = key_edit.text().strip()
            # set_config es un classmethod y Base.__init__ captura la clave al
            # instanciar: hay que configurar ANTES de crear el motor, si no la
            # peticion sale con la clave anterior (vacia en el primer uso).
            previous_config = OpenAICompatTranslate.config
            OpenAICompatTranslate.set_config(
                {'api_keys': [key]} if key else {})
            engine = OpenAICompatTranslate()
            engine.endpoint = url
            OpenAICompatTranslate.config = previous_config
            try:
                models = engine.get_models()
            except Exception as e:
                message = (
                    'No se pudo obtener la lista de modelos.\n'
                    'Revisa la Base URL y la API key.\n\n' + str(e)[:400])
                return self.alert.pop(message, 'warning')
            model_list.clear()
            model_list.addItems(models)
            if models:
                model_list.setCurrentIndex(0)
            self.alert.pop(
                '%d modelos obtenidos. Elige uno y pulsa Guardar.'
                % len(models))

        def load_current():
            name = engine_list.currentText()
            data = self.custom_ai.get(name) or {}
            self.current_id = name
            id_edit.setDisabled(bool(name))
            id_edit.setText(name)
            display_edit.setText(data.get('alias') or '')
            url_edit.setText(data.get('endpoint') or '')
            key_edit.clear()
            model_list.clear()
            model_list.addItems(data.get('models') or [])
            model_list.setCurrentText(data.get('model') or '')

        def add_blank():
            self.current_id = ''
            id_edit.setDisabled(False)
            id_edit.clear()
            display_edit.clear()
            url_edit.clear()
            key_edit.clear()
            model_list.clear()
            id_edit.setFocus()

        def delete_current():
            name = engine_list.currentText()
            if not name or name not in self.custom_ai:
                return
            del self.custom_ai[name]
            self.engine_config.pop(name, None)
            if self.config.get('translate_engine') == name:
                self.config.update(
                    translate_engine=GoogleFreeTranslateNew.name)
            self.config.update(custom_ai_engines=self.custom_ai.copy())
            self.config.update(engine_preferences=self.engine_config.copy())
            self.config.commit()
            engine_list.removeItem(engine_list.currentIndex())

        def save_current():
            name = self.current_id or id_edit.text().strip()
            if not self.current_id:
                if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', name):
                    return self.alert.pop(
                        'El Provider ID debe ir en minusculas y sin espacios.',
                        'warning')
                if name.lower() in self.taken_names or name.lower() in [
                        n.lower() for n in self.custom_ai.keys()]:
                    return self.alert.pop(
                        'Ese Provider ID ya esta en uso.', 'warning')
            url = normalized_url()
            if not re.match(r'^https?://', url):
                return self.alert.pop(
                    'Escribe una Base URL valida (https://...).', 'warning')
            models = [
                model_list.itemText(i) for i in range(model_list.count())]
            self.custom_ai[name] = {
                'name': name,
                'alias': display_edit.text().strip() or name,
                'endpoint': url,
                'models': models,
                'model': model_list.currentText().strip()}
            key = key_edit.text().strip()
            if key:
                preference = self.engine_config.get(name) or {}
                preference.update(api_keys=[key])
                self.engine_config[name] = preference
            self.config.update(custom_ai_engines=self.custom_ai.copy())
            self.config.update(engine_preferences=self.engine_config.copy())
            self.config.commit()
            if engine_list.findText(name) == -1:
                engine_list.addItem(name)
            engine_list.setCurrentText(name)
            self.alert.pop('La configuracion se ha guardado.')

        def test_engine():
            """Prueba en vivo el motor del formulario SIN guardar nada:
            1) lista de modelos en <prefijo>/models, 2) una peticion de chat
            minima contra el endpoint con el modelo elegido."""
            url = normalized_url()
            if not re.match(r'^https?://', url):
                return self.alert.pop(
                    'Escribe una Base URL valida (https://...).', 'warning')
            key = key_edit.text().strip()
            model = model_list.currentText().strip()
            previous_config = OpenAICompatTranslate.config
            OpenAICompatTranslate.set_config(
                {'api_keys': [key]} if key else {})
            engine = OpenAICompatTranslate()
            engine.endpoint = url
            engine.model = model or 'gpt-4o'
            # el ping no va en streaming y con idiomas fijos: lo suyo es
            # verificar conectividad, no la configuracion de idiomas real
            engine.stream = False
            engine.source_lang = 'English'
            engine.target_lang = 'Spanish'
            OpenAICompatTranslate.config = previous_config
            partes = []
            try:
                total = len(engine.get_models())
                partes.append('1) Modelos: OK (%d disponibles)' % total)
            except Exception as e:
                partes.append('1) Modelos: FALLO - %s' % str(e)[:250])
            try:
                respuesta = engine.translate(
                    'Okay, now we are listening to the radio.')
                texto = str(respuesta).strip()
                if not texto:
                    raise Exception('respuesta vacia')
                partes.append('2) Chat: OK - "%s"' % texto[:80])
            except Exception as e:
                partes.append('2) Chat: FALLO - %s' % str(e)[:250])
            todo_ok = all('FALLO' not in p for p in partes)
            self.alert.pop(
                'Prueba contra %s\n\n%s' % (url, '\n'.join(partes)),
                'info' if todo_ok else 'warning')

        def export_engines():
            if not self.custom_ai:
                return self.alert.pop(
                    'No hay motores personalizados que exportar.', 'warning')
            path, _ = QFileDialog.getSaveFileName(
                self, 'Exportar motores personalizados', '',
                'Fichero JSON (*.json)')
            if not path:
                return
            if not path.lower().endswith('.json'):
                path += '.json'
            data = {
                'tipo': 'better-translator-motores-openai',
                'version': 1,
                'motores': self.custom_ai.copy(),
                'claves': {
                    pid: (self.engine_config.get(pid) or {}).get('api_keys')
                    or [] for pid in self.custom_ai
                    if (self.engine_config.get(pid) or {}).get('api_keys')},
                'preferencias': {
                    pid: {k: v for k, v in
                          (self.engine_config.get(pid) or {}).items()
                          if k != 'api_keys'}
                    for pid in self.custom_ai
                    if self.engine_config.get(pid)},
            }
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return self.alert.pop(
                    'No se pudo escribir el fichero: %s' % e, 'error')
            self.alert.pop(
                '%d motor(es) exportados a:\n%s\n\nOJO: el fichero '
                'contiene las claves en claro. Guardalo en una carpeta '
                'privada.' % (len(self.custom_ai), path), 'info')

        def import_engines():
            path, _ = QFileDialog.getOpenFileName(
                self, 'Importar motores personalizados', '',
                'Fichero JSON (*.json)')
            if not path:
                return
            try:
                with open(path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as e:
                return self.alert.pop(
                    'No se pudo leer el fichero: %s' % e, 'error')
            motores = data.get('motores') if isinstance(data, dict) else None
            if not isinstance(motores, dict) or not motores:
                return self.alert.pop(
                    'El fichero no lleva la seccion "motores": no parece '
                    'una exportacion de este formulario.', 'warning')
            ocupados = [
                str(n).lower() for n in
                list(self.custom_ai.keys()) + list(self.taken_names)]
            nuevos = {}
            rechazados = []
            for pid, datos in motores.items():
                if not isinstance(pid, str) or not isinstance(datos, dict) \
                        or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', pid) \
                        or pid.lower() in ocupados \
                        or (datos.get('name') and datos['name'] != pid):
                    rechazados.append(str(pid))
                    continue
                nuevos[pid] = {
                    'name': pid,
                    'alias': datos.get('alias') or pid,
                    'endpoint': datos.get('endpoint') or '',
                    'models': list(datos.get('models') or []),
                    'model': datos.get('model') or ''}
            if rechazados:
                return self.alert.pop(
                    'No se importo nada. IDs problematicos (mal escritos, '
                    'duplicados o reservados): %s.' %
                    ', '.join(rechazados), 'warning')
            claves = data.get('claves') or {}
            preferencias = data.get('preferencias') or {}
            for pid, datos in nuevos.items():
                self.custom_ai[pid] = datos
                preference = self.engine_config.get(pid) or {}
                if claves.get(pid):
                    preference.update(api_keys=list(claves[pid]))
                extra = preferencias.get(pid)
                if isinstance(extra, dict):
                    preference.update({
                        k: v for k, v in extra.items() if k != 'api_keys'})
                if preference:
                    self.engine_config[pid] = preference
            self.config.update(custom_ai_engines=self.custom_ai.copy())
            self.config.update(engine_preferences=self.engine_config.copy())
            self.config.commit()
            engine_list.blockSignals(True)
            engine_list.clear()
            engine_list.addItems(
                sorted(self.custom_ai.keys(), key=sorted_mixed_keys))
            engine_list.blockSignals(False)
            if engine_list.count() > 0:
                load_current()
            self.alert.pop(
                '%d motor(es) importados y guardados.' % len(nuevos), 'info')

        engine_list.currentTextChanged.connect(load_current)
        engine_add.clicked.connect(add_blank)
        engine_del.clicked.connect(delete_current)
        fetch_models.clicked.connect(fetch_list)
        save_engine.clicked.connect(save_current)
        probar_engine.clicked.connect(test_engine)
        exportar_engines.clicked.connect(export_engines)
        importar_engines.clicked.connect(import_engines)
        set_shortcut(save_engine, 'save', save_current, save_engine.text())

        if engine_list.count() > 0:
            load_current()
        else:
            add_blank()

    def done(self, result):
        QDialog.done(self, result)
        self.parent.raise_()
        self.parent.activateWindow()
