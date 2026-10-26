# Better Translator para Calibre

[English](README.md) · [Descargar](https://github.com/barraco002/better-translator-calibre/releases/latest)

Traduce libros desde Calibre, conserva el original junto a la traducción o exporta
solo el texto traducido. Es un fork GPL v3 de **Ebook Translator v2.4.2**, creado
por [bookfere.com](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin).

## Instalación

1. Descarga **Better-Translator-v1.1.0.zip** desde
   [Releases](https://github.com/barraco002/better-translator-calibre/releases/latest).
2. En Calibre: **Preferencias → Complementos → Cargar complemento de archivo**.
   Elige el ZIP sin descomprimirlo. El ZIP de código fuente de GitHub es distinto.
3. Reinicia Calibre. Si falta el botón, añade **Traducir libro / Translate Book** en
   **Preferencias → Barras de herramientas y menús**.
4. Abre **Ajustes / Setting**, configura el proveedor, su clave si hace falta y el
   idioma de destino. Empieza por un libro corto en modo avanzado.

Requiere **Calibre 6.0 o superior**. La verificación local usa Windows y Calibre 9.16;
CI comprueba Calibre 6.0 y 9.16. No se probaron otros sistemas operativos ni servicios
de pago en vivo para esta versión.

## Novedades de 1.1.0

- Corrige bloqueos al cancelar trabajos o fallar la escritura de resultados.
- Permite cancelar durante las esperas de reintento y entre fragmentos del streaming.
  Una petición HTTP que ya está en curso puede esperar hasta su timeout.
- Detecta streaming cortado, respuestas vacías y traducciones truncadas.
  Reintenta el párrafo completo sin guardar texto parcial como traducción válida.
- Respeta `Retry-After` y coordina la pausa entre los trabajadores del mismo libro.
- Corrige el doble conteo de progreso y el estado al volver a traducir.
- Aísla los proveedores personalizados y sus preferencias.
- Añade pruebas automáticas, conversión de EPUB con API local, ZIP reproducible
  y SHA-256. [Detalle de validación](docs/VALIDATION.md).

Conserva edición avanzada, lotes, caché, glosarios y los motores del proyecto original.
La disponibilidad y el coste dependen del proveedor elegido.

El fork tiene ajustes y caché propios; configura sus claves por separado.
El proveedor recibe los párrafos que le envías a traducir. Las claves y la caché
se guardan localmente: revisa tus registros antes de compartirlos. La traducción
automática necesita revisión humana.

**Abrir carpeta de salida al terminar** es opcional y viene desactivado.

Créditos: **bookfere.com**, proyecto original; **barraco002**, mejoras del fork.
[GPL v3](LICENSE) · [Informar de un fallo](https://github.com/barraco002/better-translator-calibre/issues)
