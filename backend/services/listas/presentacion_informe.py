"""Presentación del resultado conservado. No consulta listas ni calcula niveles."""
from html import escape
import json

ETIQUETAS = {
    "COMPLETADA": "Completada", "PARCIAL": "Parcial", "FALLIDA": "Fallida",
    "INDETERMINADA": "Indeterminada", "CON_CANDIDATOS": "Candidatos para revisión humana",
    "SIN_CANDIDATOS": "Sin candidatos en las fuentes consultadas", "NO_CONCLUYENTE": "Resultado no concluyente",
    "PERSONA": "Persona natural", "ENTIDAD": "Empresa", "NO_DETERMINADO": "No determinado",
    "CONTRAPARTE": "Contraparte", "REPRESENTANTE": "Representante",
    "COINCIDE": "Coincide", "COMPATIBLE": "Compatible", "DIFERENTE": "Diferente",
    "AUSENTE": "Dato faltante", "NO_APLICADO": "No aplicado",
    "CONFIRMADO": "Confirmado", "REPORTADO": "Reportado", "DESCONOCIDO": "Desconocido", "FALSO": "Falso",
    "nombre": "Nombre", "identificadores": "Documentos e identificadores",
    "fecha_nacimiento": "Fecha de nacimiento", "fecha_expedicion": "Fecha de expedición",
    "nacionalidades": "Nacionalidades", "ciudadanias": "Ciudadanías", "ubicacion": "Ubicación",
    "ubicaciones": "Ubicaciones", "tipo_sujeto": "Tipo de sujeto", "observacion": "Observación",
}


def texto(valor):
    return escape(str(valor)) if valor is not None else "No informado"


def etiqueta(valor):
    return ETIQUETAS.get(valor, str(valor).replace("_", " ").capitalize())


def valor_visible(valor):
    if valor is None or valor == [] or valor == "":
        return "No informado"
    if isinstance(valor, list):
        return "; ".join(valor_visible(v) for v in valor) or "No informado"
    if isinstance(valor, dict):
        if "anio" in valor:
            return "-".join(str(valor[k]).zfill(4 if k == "anio" else 2) for k in ("anio", "mes", "dia") if valor.get(k) is not None)
        if "original" in valor:
            return f"{_normalizar_fecha_json(valor['original'])} · Precisión: {valor.get('precision', 'No informada')} · Aproximada: {'Sí' if valor.get('aproximada') else 'No'}"
        campos = ("tipo", "valor", "pais_emisor", "digito_verificacion", "rol", "texto", "pais", "historica")
        return "; ".join(f"{etiqueta(k)}: {valor_visible(valor[k])}" for k in campos if valor.get(k) is not None) or "No interpretado"
    return str(valor)


def _normalizar_fecha_json(valor):
    """Convierte un valor_fuente con JSON heredado de DatePeriod a fecha legible."""
    if not isinstance(valor, str) or not valor.startswith("{"):
        return valor
    try:
        nodo = json.loads(valor)
    except (json.JSONDecodeError, TypeError):
        return valor
    if not isinstance(nodo, dict) or nodo.get("etiqueta") != "DatePeriod":
        return valor
    puntos = []
    for borde in nodo.get("hijos", []):
        if borde.get("etiqueta") not in ("Start", "End"):
            continue
        for punto in borde.get("hijos", []):
            if punto.get("etiqueta") not in ("From", "To"):
                continue
            componentes = {h["etiqueta"]: h.get("texto", "") for h in punto.get("hijos", [])}
            anio = componentes.get("Year", "")
            if not anio:
                continue
            partes = [anio.zfill(4)]
            mes = componentes.get("Month", "")
            if mes:
                partes.append(mes.zfill(2))
                dia = componentes.get("Day", "")
                if dia:
                    partes.append(dia.zfill(2))
            puntos.append("-".join(partes))
    if not puntos:
        return valor
    unicos = list(dict.fromkeys(puntos))
    aproximada = any(
        b.get("atributos", {}).get("Approximate") in ("true", "1")
        for b in nodo.get("hijos", []) if b.get("etiqueta") in ("Start", "End"))
    prefijo = "~" if aproximada else ""
    return f"{prefijo}{unicos[0]}" if len(unicos) == 1 else f"{prefijo}{unicos[0]} a {unicos[-1]}"


def filas(pares):
    return "<dl>" + "".join(f"<dt>{texto(nombre)}</dt><dd>{texto(valor)}</dd>" for nombre, valor in pares) + "</dl>"


def referencia(dato):
    origen = dato.get("referencia") or {}
    return filas([( "Campo original", origen.get("campo_original")), ("Identidad de origen", origen.get("identidad_origen"))]) if origen else ""


def presentar_candidato(candidato, fuentes):
    fuente = fuentes.get(candidato["cobertura_id"], {})
    contenido = f"<section><h2>{texto(candidato['nombre_principal'])}</h2>"
    contenido += filas([("Clasificación de coincidencia", candidato["nivel"]), ("Explicación", candidato["explicacion"]),
        ("Revisión prioritaria", "Sí" if candidato.get("revision_prioritaria") else "No"),
        ("Tipo de sujeto", etiqueta(candidato["tipo_sujeto"])), ("Fuente", fuente.get("nombre_origen")),
        ("Versión consultada", fuente.get("version_id")), ("Registro", candidato.get("registro_id")),
        ("Regla aplicada", candidato["regla_codigo"]), ("Versión de reglas", candidato["regla_version"]),
        ("Versión de algoritmo", candidato["algoritmo_version"])])
    contenido += "<h3>Comparación de datos</h3>"
    for motivo in candidato["motivos"]:
        contenido += filas([("Campo", etiqueta(motivo["campo"])), ("Resultado", etiqueta(motivo["resultado"])),
            ("Dato consultado", motivo.get("valor_consultado")), ("Dato de la fuente", _normalizar_fecha_json(motivo.get("valor_fuente"))),
            ("Explicación", motivo["explicacion"]), ("Calidad publicada", etiqueta(motivo.get("calidad_fuente", "DESCONOCIDO"))),
            ("Método", motivo["metodo"])]) + referencia(motivo)
    contenido += "<h3>Información conservada de la fuente</h3>"
    for nombre in candidato.get("nombres", []):
        contenido += filas([("Nombre o alias", nombre["valor"]), ("Tipo", nombre["tipo"]),
            ("Alias débil", "Sí" if nombre["alias_debil"] else "No"), ("Calidad", etiqueta(nombre["calidad"]))]) + referencia(nombre)
    for documento in candidato.get("identificadores", []):
        contenido += filas([("Documento", valor_visible(documento)), ("Calidad", etiqueta(documento["calidad"]))]) + referencia(documento)
    for hecho in candidato.get("hechos", []):
        contenido += filas([(etiqueta(hecho["campo"]), valor_visible(hecho["valor"])),
                            ("Calidad", etiqueta(hecho["calidad"]))]) + referencia(hecho)
    for relacion in candidato.get("relaciones", []):
        contenido += filas([("Relación publicada", relacion["tipo"]), ("Dirección", relacion["direccion"]),
            ("Fuente relacionada", relacion["fuente_destino"]), ("Versión relacionada", relacion["version_destino_id"]),
            ("Registro relacionado", relacion["registro_destino_id"])]) + referencia(relacion)
    if candidato.get("relaciones"):
        contenido += "<p>Una relación publicada no confirma identidad ni implica sanción o riesgo por asociación.</p>"
    return contenido + "</section>"


def presentar_informe(datos):
    from services.listas.informes import calcular_huella
    resultado, contexto = datos["resultado"], datos.get("contexto", {})
    fuentes = {f["id"]: f for f in resultado["cobertura"]}
    contenido = "<h1>Informe de consulta de listas cautelares</h1>"
    contenido += "<p>Las posibles coincidencias requieren revisión humana. No determinan aprobación, rechazo, sanción aplicable ni nivel de riesgo.</p>"
    contenido += "<p>Este informe conserva el resultado de la consulta. Las revisiones humanas posteriores se consultan por separado en el historial.</p>"
    contenido += filas([("Consulta", resultado["consulta_id"]), ("Expediente", contexto.get("expediente_id")),
        ("Sujeto consultado", etiqueta(contexto.get("sujeto_rol", "No informado"))),
        ("Estado", etiqueta(resultado["estado_ejecucion"])), ("Resultado", etiqueta(resultado["conclusion_busqueda"])),
        ("Fecha de consulta", resultado["fecha_inicio"]), ("Fecha de finalización", resultado.get("fecha_fin")),
        ("Proveedor", resultado["proveedor"])])
    contenido += "<h2>Criterios utilizados</h2>" + filas([(etiqueta(k), valor_visible(v)) for k,v in datos["criterio"].items() if v is not None and v != []])
    contenido += "<h2>Fuentes y versiones consultadas</h2>"
    for fuente in fuentes.values():
        contenido += filas([("Fuente", fuente["nombre_origen"]), ("Código", fuente.get("fuente_codigo")),
            ("Estado de cobertura", fuente["estado"]), ("Versión", fuente.get("version_id")),
            ("Revisión activa al admitir", fuente.get("revision_activa")), ("Hash del contenido", fuente.get("hash_contenido")),
            ("Motivo", fuente.get("motivo"))])
    for aviso in (*resultado.get("advertencias", []), *resultado.get("criterios_no_aplicados", [])):
        contenido += f"<p><strong>Advertencia:</strong> {texto(aviso['descripcion'])}</p>"
    for candidato in resultado["candidatos"]:
        contenido += presentar_candidato(candidato, fuentes)
    if not resultado["candidatos"]:
        contenido += "<p>No se presentan candidatos. Esto no constituye aprobación ni certificación de ausencia de riesgo.</p>"
    if resultado.get("error"):
        contenido += filas([("Error de consulta", resultado["error"]["mensaje"]), ("Código", resultado["error"]["codigo"])])
    manifiesto = datos.get("manifiesto", {})
    trazabilidad = manifiesto.get("busqueda", {})
    contenido += "<h2>Trazabilidad del informe</h2>" + filas([
        ("Generador", datos["version_generador"]), ("Hash del resultado", calcular_huella(resultado)),
        ("Hash del manifiesto", calcular_huella(manifiesto)), ("Política", trazabilidad.get("politica_version")),
        ("Versión de reglas", trazabilidad.get("reglas_version")), ("Versión de algoritmo", trazabilidad.get("algoritmo_version")),
        ("Hash de catálogo", trazabilidad.get("catalogos_hash")), ("Hash de parámetros", trazabilidad.get("parametros_internos_hash"))])
    for fuente in trazabilidad.get("fuentes", []):
        contenido += filas([("Fuente", fuente["fuente_codigo"]), ("Generación de búsqueda", fuente["generacion_id"]),
            ("Hash de generación", fuente["generacion_hash"]), ("Adaptador", fuente["version_adaptador"]),
            ("Normalización", fuente["version_normalizacion"])])
    return '<html lang="es"><meta charset="utf-8"><style>@page {size:A4; margin:18mm} body {font-family:sans-serif; font-size:10pt; color:#17212b} h1 {font-size:18pt} h2 {font-size:13pt; margin-top:20pt} dt {font-weight:bold; margin-top:5pt} dd {margin-left:0; overflow-wrap:anywhere; white-space:pre-wrap} h2,h3,dt {break-after:avoid} dl {margin:8pt 0} </style><body>' + contenido + '</body></html>'
