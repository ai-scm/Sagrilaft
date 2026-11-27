"""Informe interno a partir de un resultado conservado, sin volver a consultar listas."""
import hashlib
import html
import json

VERSION_GENERADOR = "informe-listas-v1"
VERSION_GENERADOR_F6 = "informe-listas-f6-v2"
# Tusdatos (contrato `tusdatos-1`): constancia técnica de auditoría interna. El informe para leer es
# el PDF oficial de Tusdatos (evidencia PDF_PROVEEDOR); esta constancia no lo reemplaza.
VERSION_CONSTANCIA_TUSDATOS = "constancia-tusdatos-v1"


def version_informe(resultado):
    if resultado.get("version_contrato") == "tusdatos-1":
        return VERSION_CONSTANCIA_TUSDATOS
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

    version = version_informe(datos["resultado"])
    if version == VERSION_GENERADOR_F6:
        from services.listas.presentacion_informe import presentar_informe
        return HTML(string=presentar_informe(datos)).write_pdf()
    if version == VERSION_CONSTANCIA_TUSDATOS:
        return HTML(string=_constancia_tusdatos(datos)).write_pdf()

    contenido = html.escape(json.dumps(datos, ensure_ascii=False, indent=2))
    documento = (
        '<html lang="es"><meta charset="utf-8"><style>'
        '@page {size:A4; margin:20mm} pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:9pt}'
        '</style><h1>Informe de consulta de listas</h1>'
        '<p>Los candidatos requieren revisión humana. Este informe no decide sanciones ni riesgo.</p>'
        f'<pre>{contenido}</pre></html>'
    )
    return HTML(string=documento).write_pdf()


def _constancia_tusdatos(datos: dict) -> str:
    """Constancia técnica de una consulta a Tusdatos: qué se consultó, qué concluyó el sistema y cuándo."""
    resultado = datos["resultado"]
    contenido = html.escape(json.dumps(datos, ensure_ascii=False, indent=2))
    resumen = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in (
        ("Consulta", resultado.get("consulta_id")), ("Estado", resultado.get("estado_ejecucion")),
        ("Conclusión del sistema", resultado.get("conclusion_busqueda")),
        ("Inicio", resultado.get("fecha_inicio")), ("Cierre", resultado.get("fecha_fin")),
    ) if v)
    return (
        '<html lang="es"><meta charset="utf-8"><style>'
        '@page {size:A4; margin:20mm} body {font-family:sans-serif; font-size:10pt}'
        '.aviso {border:1px solid #999; padding:8px 10px; background:#f3f3f3}'
        'table {border-collapse:collapse; margin:10px 0} th,td {text-align:left; padding:3px 10px 3px 0; vertical-align:top}'
        'pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:8pt}'
        '</style><h1>Constancia técnica del sistema</h1>'
        '<p class="aviso"><strong>Documento de auditoría interna de SAGRILAFT. No es el informe oficial.</strong> '
        'El reporte oficial de la consulta es el PDF que entrega Tusdatos. Esta constancia la genera el sistema al '
        'cerrar la consulta para dejar registro, sin posibilidad de cambios, de los datos consultados, de lo que '
        'respondió el proveedor (solo las fuentes SAGRILAFT) y de lo que concluyó el sistema. Los candidatos '
        'requieren revisión humana; este documento no decide sanciones ni riesgo.</p>'
        f'<table>{resumen}</table>'
        '<h2>Registro técnico (JSON)</h2>'
        f'<pre>{contenido}</pre></html>'
    )
