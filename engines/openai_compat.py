from .openai import ChatgptTranslate

load_translations()  # type: ignore


class OpenAICompatTranslate(ChatgptTranslate):
    """Motor OpenAI-compatible definido por el usuario.

    Es la pieza generica detras del formulario "OpenAI API" del dialogo de
    configuracion (equivalente al flujo "add provider" tipo harness):
      Provider ID  -> cls.name   (clave en custom_ai_engines / preferencias)
      Display name -> cls.alias  (etiqueta visible)
      Base URL     -> cls.endpoint (https://host/v1/chat/completions)
      Fetch models -> get_models() heredado de engines/openai.py
                      (consulta <prefijo>/models con la clave en Bearer)
    name/alias/endpoint/models/model se inyectan con set_engine_data() desde
    la entrada correspondiente de "custom_ai_engines", al estilo de como
    CustomTranslate consume sus plantillas JSON. El prompt, el muestreo, el
    stream y las claves multiples son herencia de ChatgptTranslate.
    """

    name = 'OpenAI-compatible'
    alias = 'OpenAI-compatible'
    endpoint = 'https://api.openai.com/v1/chat/completions'

    concurrency_limit = 1
    request_interval = 1.0
    request_timeout = 60.0
    temperature = 0.2

    models: list[str] = []
    model: str | None = ''

    @classmethod
    def set_engine_data(cls, data):
        cls.name = data.get('name')  # Provider ID del proveedor del usuario
        cls.alias = data.get('alias') or cls.name
        cls.endpoint = data.get('endpoint') or cls.endpoint
        cls.models = list(data.get('models') or [])
        cls.model = data.get('model') or ''
