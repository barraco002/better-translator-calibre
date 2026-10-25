from .openai import ChatgptTranslate

load_translations()  # type: ignore


class RadoxTranslate(ChatgptTranslate):
    # Motor "proveedor personalizado" en el estilo del formulario del harness:
    #   Provider ID   -> name  = 'Radox'  (identificador interno, minusculas)
    #   Display name  -> alias = 'Radox AI (OpenAI-compatible)' (en el selector)
    #   Base URL      -> endpoint (editable ademas en el campo Endpoint de la UI)
    #   API protocol  -> OpenAI Chat Completions (heredado de ChatgptTranslate)
    #   API key       -> campo "API keys" del motor (se pega en la UI)
    #   Fetch models  -> boton "Refresh" heredado de engines/openai.py
    #                    (get_models consulta <prefijo>/models con Bearer)
    # Los valores por defecto replican la casa: temperatura 0.2, un envio por
    # vez, intervalo 1 s y timeout 60 s. La lista de modelos nace VACIA a
    # proposito: asi el boton Refresh queda visible y el "+ fetch" es el flujo
    # natural (pegar clave -> Refresh -> elegir modelo). Mientras la lista este
    # vacia, la casilla "Custom" permite teclear el ID a mano.
    name = 'Radox'
    alias = 'Radox AI (OpenAI-compatible)'
    endpoint = 'https://api.radoxai.com/v1/chat/completions'

    concurrency_limit = 1
    request_interval = 1.0
    request_timeout = 60.0
    temperature = 0.2

    models: list[str] = []
    model: str | None = ''
