# Catálogos oficiales de Tusdatos

Copias de los catálogos que Tusdatos publica en su ambiente de pruebas (indicados en la
documentación de `GET /api/report_json/{id}`). Se guardan aquí para no depender de que el
sandbox siga en línea. Descargados el 2026-11-25 con el usuario de pruebas publicado.

| Archivo | Origen | Contenido |
|---|---|---|
| `hallazgos.json` | `GET /api/fuentes-disponibles` | código de hallazgo → descripción (261) |
| `fuentes.json` | `GET /api/fuentes-colombia` | código de fuente → nombre oficial (111) |
| `errores.json` | `GET /api/catalogo-errores-fuentes` | código del campo `errores` → fuente (139) |

Tusdatos indica usar siempre el **código** (estable) y no el texto, que puede cambiar.
Para actualizarlos, volver a descargarlos y revisar el diff.
