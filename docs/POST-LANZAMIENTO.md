# Quería traducir un ebook. Terminé depurando una cola que no sabía terminar.

El plan era modesto: mejorar mi traductor de Calibre.

Como manda la tradición, el plan dejó de ser modesto en cuanto apareció `asyncio`.

Acabo de publicar **Better Translator 1.1.0**, mi fork de Ebook Translator de
bookfere.com. El mérito de la base es suyo; esta entrega se concentra en que los
trabajos terminen de forma predecible.

Había tres villanos con bastante personalidad:

- El contador de progreso avanzaba también cuando las métricas lo consultaban.
  Observar el progreso alteraba el progreso. Física cuántica de barra de carga.
- Si se cortaba el streaming, un bucle podía seguir esperando contenido que ya
  nunca iba a llegar.
- Cancelar un trabajador o fallar al guardar un resultado podía dejar una cola
  esperando para siempre. Un `join()` con aspiraciones de proceso residente.

La versión nueva corrige esos casos, reintenta párrafos completos sin dar por buena
una respuesta parcial, respeta `Retry-After`, aísla proveedores personalizados y
cierra sus trabajadores al terminar. Las esperas de reintento se pueden cancelar;
las peticiones HTTP que ya están en vuelo siguen sujetas a su timeout.

También hay una prueba que levanta una API local, convierte un EPUB de ejemplo y
comprueba el resultado. Porque «en mi máquina funciona» mejora bastante cuando
tu máquina tiene que demostrarlo sin una API de pago ni tus libros privados.

No voy a poner «traducción perfecta» en el README. Las pruebas verifican software;
la calidad de una traducción todavía exige leerla.

[Código y pruebas](https://github.com/barraco002/better-translator-calibre)
· [ZIP instalable y checksum](https://github.com/barraco002/better-translator-calibre/releases/tag/v1.1.0)
· [Qué se verificó y qué queda fuera](https://github.com/barraco002/better-translator-calibre/blob/main/docs/VALIDATION.md)

GPL v3, con créditos al proyecto original. Sin benchmark inventado y sin cambiar
el mundo. Hoy tocaba conseguir que una cola dejara de esperar.
