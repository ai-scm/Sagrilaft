"""Informe interno a partir de un resultado conservado, sin volver a consultar listas."""
import hashlib
import html
import json

VERSION_GENERADOR = "informe-listas-v1"
VERSION_GENERADOR_F6 = "informe-listas-f6-v2"


def version_informe(resultado):
    version = resultado.get("generador_informe_version", VERSION_GENERADOR) if resultado.get("version_contrato") == "2.1" else VERSION_GENERADOR
    if version not in {VERSION_GENERADOR, VERSION_GENERADOR_F6}:
        raise ValueError("Generador de informe no disponible; no se sustituye")
    return version


def serializar_canonico(datos: dict) -> bytes:
    return json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def calcular_huella(datos: dict) -> str:
    return hashlib.sha256(serializar_canonico(datos)).hexdigest()


def generar_informe_pdf(datos: dict) -> bytes:
    from weasyprint import HTML

    if version_informe(datos["resultado"]) == VERSION_GENERADOR_F6:
        from services.listas.presentacion_informe import presentar_informe
        return HTML(string=presentar_informe(datos)).write_pdf()

    contenido = html.escape(json.dumps(datos, ensure_ascii=False, indent=2))
    documento = (
        '<html lang="es"><meta charset="utf-8"><style>'
        '@page {size:A4; margin:20mm} pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:9pt}'
        '</style><h1>Informe de consulta de listas</h1>'
        '<p>Los candidatos requieren revisión humana. Este informe no decide sanciones ni riesgo.</p>'
        f'<pre>{contenido}</pre></html>'
    )
    return HTML(string=documento).write_pdf()
