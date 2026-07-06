"""
Exportación del formulario a PDF (versión imprimible).

Objetivo de dominio:
  - Generar un PDF legible y presentable a partir de la información del formulario.
  - Mantener consistencia visual con el frontend (paleta, tipografía, cards, layout).
  - Guardar el archivo en el directorio de uploads del formulario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from domain.formulario.entidades import FormularioDatos
from domain.utils.fechas import NOMBRES_MESES_ES
from services.formulario.formato_moneda import formatear_monto_monetario
from services.formulario.serializacion import formulario_a_dict as deserializar_campos_json

# ─── Campos financieros de monto con sus etiquetas (en orden de presentación) ─
_CAMPOS_FINANCIEROS: List[Tuple[str, str]] = [
    ("Ingresos Mensuales",  "ingresos_mensuales"),
    ("Otros Ingresos",      "otros_ingresos"),
    ("Egresos Mensuales",   "egresos_mensuales"),
    ("Total Activos",       "total_activos"),
    ("Total Pasivos",       "total_pasivos"),
    ("Patrimonio",          "patrimonio"),
]

_RAZON_SOCIAL_EMPRESA = os.getenv("VITE_RAZON_SOCIAL", "HIGH TECH SOFTWARE S.A.S.")
_CORREO_DATOS_PERSONALES = os.getenv("VITE_CORREO_DATOS", "administrativocol@blend360.com")


# ─── Tipos del dominio ────────────────────────────────────────────────────────

class DependenciaPdfNoInstaladaError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchivoPdfGenerado:
    nombre_archivo: str
    ruta_archivo: Path


# ─── Presentación de valores ──────────────────────────────────────────────────

_VALORES_AMIGABLES: Dict[str, str] = {
    "si": "Sí",
    "no": "No",
    "juridica": "Jurídica",
    "natural": "Natural",
    "proveedor": "Proveedor",
    "cliente": "Cliente",
    "vinculacion": "Vinculación",
    "actualizacion": "Actualización",
    "c": "Comercializador",
    "d": "Distribuidor",
    "r": "Representante",
    "f": "Fabricante",
    "i": "Importador",
    "cuenta_corriente": "Cuenta corriente",
    "cuenta_ahorros": "Cuenta ahorros",
    "importacion": "Importación",
    "exportacion": "Exportación",
    "inversiones": "Inversiones",
    "pago_servicios": "Pago de servicios",
    "otras": "Otras",
}


def _valor_a_texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (int, float)):
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        return format(valor, ",").replace(",", ".")
    if isinstance(valor, (list, tuple)):
        return ", ".join(_valor_a_texto(v) for v in valor if _valor_a_texto(v))
    if isinstance(valor, str):
        normalizado = valor.strip()
        return _VALORES_AMIGABLES.get(normalizado.lower(), normalizado)
    return str(valor).strip()


def _formatear_monto(valor: Any, moneda: str, moneda_otra: Any = None) -> str:
    """
    Formatea un valor numérico monetario aplicando el separador de miles
    correcto según la moneda seleccionada (espejo exacto de CurrencyInput.jsx).

    Retorna el valor precedido del símbolo de la moneda, con los separadores
    de miles adecuados al locale de la moneda.

    Ejemplos:
        COP  → $ 1.500.000
        USD  → US$ 1,500,000
        EUR  → € 1.500.000
        PEN  → S/ 1,500,000
    """
    return formatear_monto_monetario(valor, moneda, moneda_otra)


def _normalizar_referencias_comerciales(
    filas: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Reconcilia claves históricas (nombre/contacto) con las actuales
    (nombre_establecimiento/persona_contacto) para referencias comerciales.
    """
    resultado = []
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        resultado.append({
            **fila,
            "nombre_establecimiento": fila.get("nombre_establecimiento") or fila.get("nombre"),
            "persona_contacto": fila.get("persona_contacto") or fila.get("contacto"),
        })
    return resultado


# ─── Renderizadores HTML ──────────────────────────────────────────────────────

def _fila_etiqueta_valor(etiqueta: str, valor: Any) -> str:
    texto = _valor_a_texto(valor)
    if not texto:
        return ""
    return (
        "<div class='kv'>"
        f"<div class='k'>{escape(etiqueta)}</div>"
        f"<div class='v'>{escape(texto)}</div>"
        "</div>"
    )


def _render_seccion_campos(titulo: str, pares: Sequence[Tuple[str, Any]]) -> str:
    bloques = [b for b in (_fila_etiqueta_valor(e, v) for e, v in pares) if b]
    if not bloques:
        return ""
    return (
        "<section class='card'>"
        f"<h2>{escape(titulo)}</h2>"
        "<div class='grid'>"
        f"{''.join(bloques)}"
        "</div>"
        "</section>"
    )


def _render_tabla(
    titulo: str,
    filas: Sequence[Dict[str, Any]],
    columnas: Sequence[Tuple[str, str]],
) -> str:
    filas_limpias = [f for f in filas if any(_valor_a_texto(f.get(clave)) for clave, _ in columnas)]
    if not filas_limpias:
        return ""
    encabezados = "".join(f"<th>{escape(label)}</th>" for _, label in columnas)
    cuerpo = "".join(
        "<tr>"
        + "".join(f"<td>{escape(_valor_a_texto(f.get(clave)))}</td>" for clave, _ in columnas)
        + "</tr>"
        for f in filas_limpias
    )
    return (
        "<section class='card card-tabla'>"
        f"<h2>{escape(titulo)}</h2>"
        "<div class='table-wrap'>"
        "<table>"
        f"<thead><tr>{encabezados}</tr></thead>"
        f"<tbody>{cuerpo}</tbody>"
        "</table>"
        "</div>"
        "</section>"
    )


# ─── Estilos ──────────────────────────────────────────────────────────────────

_CSS_BASE = """
    :root{
      --primary-500:#6366f1; --primary-600:#4f46e5; --primary-700:#4338ca; --primary-800:#3730a3; --primary-900:#312e81;
      --gray-50:#f8fafc; --gray-100:#f1f5f9; --gray-200:#e2e8f0; --gray-600:#475569; --gray-800:#1e293b; --gray-900:#0f172a;
      --radius-lg:16px;
    }
    @page { size: A4; margin: 18mm 14mm; }
    *{ box-sizing:border-box; }
    body{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Arial,sans-serif; color:var(--gray-800); background:var(--gray-100); line-height:1.35; }
    .header{
      background: linear-gradient(135deg, var(--gray-900) 0%, var(--primary-900) 55%, var(--primary-800) 100%);
      color:#fff; padding:18px 22px; border-radius:18px; position:relative;
    }
    .header h1{ margin:0; font-size:18px; font-weight:800; letter-spacing:-.02em; }
    .header .sub{ opacity:.75; margin-top:4px; font-size:11px; }
    .chip{
      position:absolute; top:18px; right:22px;
      background: rgba(255,255,255,.12);
      border: 1px solid rgba(255,255,255,.18);
      padding:6px 10px; border-radius:10px; font-size:10px; font-weight:700;
    }
    .content{ margin-top:14px; }
    .card{
      background:#fff; border:1px solid var(--gray-200);
      border-radius: var(--radius-lg);
      padding:14px 16px; margin: 12px 0;
    }
    .card h2{ margin:0 0 10px 0; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--gray-600); }
    .grid{ display:grid; grid-template-columns: 1fr 1fr; gap:10px 14px; }
    .kv{ border:1px solid var(--gray-200); border-radius:12px; padding:10px 10px; background:var(--gray-50); }
    .k{ font-size:10px; color:var(--gray-600); text-transform:uppercase; letter-spacing:.05em; font-weight:700; }
    .v{ margin-top:4px; font-size:11px; font-weight:600; color:var(--gray-800); white-space:pre-wrap; overflow-wrap:break-word; }
    .table-wrap{ overflow:hidden; border-radius:12px; border:1px solid var(--gray-200); }
    table{ width:100%; border-collapse:collapse; font-size:10px; table-layout:fixed; }
    thead th{ text-align:left; padding:8px 10px; background:var(--gray-50); color:var(--gray-600); text-transform:uppercase; letter-spacing:.05em; font-weight:800; border-bottom:1px solid var(--gray-200); overflow-wrap:break-word; }
    tbody td{ padding:8px 10px; border-bottom:1px solid var(--gray-200); vertical-align:top; overflow-wrap:break-word; }
    tbody tr:last-child td{ border-bottom:0; }
    .muted{ color:var(--gray-600); font-size:10px; margin-top:6px; }
    .footer{ margin-top:10px; font-size:9px; color:var(--gray-600); }
    .card{ page-break-inside:avoid; }
    .card-tabla{ page-break-inside:auto; }
    .paso{ page-break-before:always; }
    .paso-primero{ page-break-before:auto; }
    .paso-titulo{
      font-size:11px; font-weight:800; text-transform:uppercase;
      letter-spacing:.08em; color:var(--primary-600);
      border-bottom:2px solid var(--primary-500);
      padding-bottom:6px; margin:0 0 10px 0;
    }
    """


# ─── Definición declarativa de secciones ──────────────────────────────────────

@dataclass(frozen=True)
class _SeccionCampos:
    titulo: str
    campos: List[Tuple[str, str]]  # (etiqueta, clave_dato)


@dataclass(frozen=True)
class _SeccionTabla:
    titulo: str
    clave_dato: str
    columnas: List[Tuple[str, str]]  # (clave_fila, encabezado)
    transformar: Optional[Callable[..., List[Dict[str, Any]]]] = None


@dataclass(frozen=True)
class _SeccionNarrativaFirma:
    titulo: str


_SeccionFormulario = Union[_SeccionCampos, _SeccionTabla, _SeccionNarrativaFirma]


def _componer_texto_firma(datos: Dict[str, Any]) -> str:
    dia    = datos.get('dia_firma')
    mes    = datos.get('mes_firma')
    year   = datos.get('year_firma')
    ciudad = (datos.get('ciudad_firma') or '').strip()

    dia_str    = str(int(dia))  if dia    else '____'
    mes_str    = NOMBRES_MESES_ES[int(mes) - 1] if mes and 1 <= int(mes) <= 12 else '_____________'
    year_str   = str(int(year)) if year   else '_______'
    ciudad_str = ciudad         if ciudad else '___________________'

    return (
        f"En constancia de haber leído y acatado lo anterior firmo el presente documento "
        f"a los {dia_str} días del mes de {mes_str} "
        f"de {year_str} en la ciudad de {ciudad_str}."
    )


def _render_narrativa_firma(titulo: str, datos: Dict[str, Any]) -> str:
    texto = escape(_componer_texto_firma(datos))
    # {{S:R1*}} es el text tag nativo de ZohoSign para firma obligatoria del primer firmante.
    # SIN overflow:hidden → WeasyPrint incluye todos los espacios en la capa de texto del PDF
    # → ZohoSign mide el ancho real del tag y crea el campo de firma a ese ancho.
    # font-size:24px → cada espacio es más ancho en el PDF → campo más amplio.
    # Color blanco = invisible en impresión.
    _espacios = " " * 120
    linea_firma = (
        "<div style='margin-top:24px;'>"
        "<div style='font-size:11px; color:var(--gray-800); margin-bottom:6px;'>"
        "Firma Representante Legal"
        "</div>"
        f"<div style='border-bottom:1.5px solid var(--gray-800); color:white;"
        f"            font-size:24px; white-space:nowrap; min-height:70px;'>"
        f"{{{{S:R1*{_espacios}}}}}"
        f"</div>"
        "</div>"
    )
    return (
        "<section class='card' style='page-break-before:always;'>"
        f"<h2>{escape(titulo)}</h2>"
        f"<p style='font-size:11px; color:var(--gray-800); line-height:1.7;'>{texto}</p>"
        f"{linea_firma}"
        "</section>"
    )


@dataclass(frozen=True)
class _PasoFormulario:
    numero: int
    titulo: str
    secciones: List[_SeccionFormulario]


_PASOS_FORMULARIO: List[_PasoFormulario] = [
    _PasoFormulario(2, "Clasificación e Información Básica", [
        _SeccionCampos("Clasificación", [
            ("Tipo de contraparte",       "tipo_contraparte"),
            ("Tipo de persona",           "tipo_persona"),
            ("Tipo de solicitud",         "tipo_solicitud"),
            ("Clasificación de actividad","clasificacion_actividad"),
        ]),
        _SeccionCampos("Información Básica", [
            ("Razón social",              "razon_social"),
            ("Tipo de identificación",    "tipo_identificacion"),
            ("Número de identificación",  "numero_identificacion"),
            ("Dígito de verificación",    "digito_verificacion"),
            ("Dirección",                 "direccion"),
            ("País",                      "pais"),
            ("Departamento",              "departamento"),
            ("Ciudad",                    "ciudad"),
            ("Teléfono",                  "telefono"),
            ("Fax",                       "fax"),
            ("Correo",                    "correo"),
            ("Código ICA",                "codigo_ica"),
            ("Página web",                "pagina_web"),
        ]),
    ]),
    _PasoFormulario(3, "Representante Legal", [
        _SeccionCampos("Representante Legal o Persona Natural", [
            ("Nombre",                    "nombre_representante"),
            ("Tipo de documento",         "tipo_doc_representante"),
            ("Número de documento",       "numero_doc_representante"),
            ("Fecha de expedición",       "fecha_expedicion"),
            ("Ciudad de expedición",      "ciudad_expedicion"),
            ("Nacionalidad",              "nacionalidad"),
            ("Fecha de nacimiento",       "fecha_nacimiento"),
            ("Ciudad de nacimiento",      "ciudad_nacimiento"),
            ("Profesión",                 "profesion"),
            ("Correo",                    "correo_representante"),
            ("Teléfono",                  "telefono_representante"),
            ("Dirección (funciones)",     "direccion_funciones"),
            ("País (funciones)",          "pais_funciones"),
            ("Departamento (funciones)",  "departamento_funciones"),
            ("Ciudad (funciones)",        "ciudad_funciones"),
            ("Dirección de residencia",   "direccion_residencia"),
            ("Ciudad de residencia",      "ciudad_residencia"),
        ]),
    ]),
    _PasoFormulario(4, "Junta Directiva y Accionistas", [
        _SeccionTabla("Junta Directiva y Representantes", "junta_directiva", [
            ("cargo",       "Cargo"),
            ("nombre",      "Nombre"),
            ("tipo_id",     "Tipo ID"),
            ("numero_id",   "Número ID"),
            ("es_pep",      "¿PEP?"),
            ("vinculos_pep","Vínculos PEP"),
        ]),
        _SeccionTabla("Composición Accionaria", "accionistas", [
            ("nombre",      "Nombre"),
            ("porcentaje",  "% Participación"),
            ("tipo_id",     "Tipo ID"),
            ("numero_id",   "Número ID"),
            ("es_pep",      "¿PEP?"),
            ("vinculos_pep","Vínculos PEP"),
        ]),
        _SeccionTabla("Beneficiario Final", "beneficiario_final", [
            ("nombre",      "Nombre"),
            ("porcentaje",  "% Control"),
            ("tipo_id",     "Tipo ID"),
            ("numero_id",   "Número ID"),
            ("es_pep",      "¿PEP?"),
            ("vinculos_pep","Vínculos PEP"),
        ]),
    ]),
    _PasoFormulario(5, "Información Financiera y Referencias", [
        _SeccionCampos("Información Financiera", [
            ("Moneda de Declaración",         "moneda_declaracion"),
            ("Actividad Económica Principal", "actividad_economica"),
            ("Código CIIU",                   "codigo_ciiu"),
            ("Ingresos Mensuales",            "ingresos_mensuales"),
            ("Otros Ingresos",                "otros_ingresos"),
            ("Egresos Mensuales",             "egresos_mensuales"),
            ("Total Activos",                 "total_activos"),
            ("Total Pasivos",                 "total_pasivos"),
            ("Patrimonio",                    "patrimonio"),
        ]),
        _SeccionTabla("Referencias Comerciales", "referencias_comerciales", [
            ("nombre_establecimiento", "Nombre del establecimiento"),
            ("persona_contacto",       "Persona a contactar"),
            ("telefono",               "Teléfono"),
            ("ciudad",                 "Ciudad"),
        ], _normalizar_referencias_comerciales),
        _SeccionTabla("Referencias Bancarias", "referencias_bancarias", [
            ("entidad",  "Entidad"),
            ("producto", "Producto"),
        ]),
    ]),
    _PasoFormulario(6, "Moneda Extranjera y Régimen Tributario", [
        _SeccionCampos("Operaciones en Moneda Extranjera", [
            ("¿Realiza operaciones en moneda extranjera?", "realiza_operaciones_moneda_extranjera"),
            ("Países de operaciones",                      "paises_operaciones"),
            ("Tipos de transacción",                       "tipos_transaccion"),
            ("Otros tipos de transacción",                 "tipos_transaccion_otros"),
        ]),
        _SeccionCampos("Clasificación de la Empresa y Régimen Tributario", [
            ("Actividad (clasificación)",          "actividad_clasificacion"),
            ("¿Cual? Especifique",                 "actividad_especifica"),
            ("Sector",                             "sector"),
            ("Vigilado por la Superintendencia de","superintendencia"),
            ("Responsabilidades renta",            "responsabilidades_renta"),
            ("Autorretenedor",                     "autorretenedor"),
            ("Responsabilidades IVA",              "responsabilidades_iva"),
            ("Régimen IVA",                        "regimen_iva"),
            ("¿Es Gran Contribuyente?",            "gran_contribuyente"),
            ("Entidad sin ánimo de lucro",         "entidad_sin_animo_lucro"),
            ("Retención de Industria y Comercio",  "retencion_ica"),
            ("Impuesto de Industria y Comercio",   "impuesto_ica"),
            ("Entidad oficial",                    "entidad_oficial"),
            ("Exento de Retención en la Fuente",   "exento_retencion_fuente"),
        ]),
    ]),
    _PasoFormulario(7, "Contactos e Información Bancaria", [
        _SeccionCampos("Persona autorizada para recepción de órdenes de compra y de servicio", [
            ("Nombre",   "contacto_ordenes_nombre"),
            ("Cargo",    "contacto_ordenes_cargo"),
            ("Teléfono", "contacto_ordenes_telefono"),
            ("Correo",   "contacto_ordenes_correo"),
        ]),
        _SeccionCampos("Persona autorizada para recepción de reportes de pago", [
            ("Nombre",   "contacto_pagos_nombre"),
            ("Cargo",    "contacto_pagos_cargo"),
            ("Teléfono", "contacto_pagos_telefono"),
            ("Correo",   "contacto_pagos_correo"),
        ]),
        _SeccionTabla("Información Bancaria para Pagos", "informacion_bancaria_pagos", [
            ("entidad_bancaria", "Banco"),
            ("ciudad_oficina",   "Ciudad oficina"),
            ("tipo_cuenta",      "Tipo De Cuenta"),
            ("numero_cuenta",    "Número cuenta"),
        ]),
    ]),
    _PasoFormulario(8, "Declaraciones y Firma", [
        _SeccionCampos("Autorizaciones y Origen de Fondos", [
            ("Autorización tratamiento de datos", "autorizacion_datos"),
            ("Declaración origen de fondos",      "declaracion_origen_fondos"),
            ("Origen de fondos (detalle)",        "origen_fondos"),
        ]),
        _SeccionNarrativaFirma("Firma Representante Legal"),
    ]),
]


# ─── Constructor HTML ─────────────────────────────────────────────────────────

def _renderizar_seccion_financiera(datos: Dict[str, Any]) -> str:
    """
    Renderiza la sección «Información Financiera» con formato de moneda correcto.

    Lee `moneda_declaracion` del snapshot y aplica símbolo + separadores de miles
    consistentes con el frontend (CurrencyInput.jsx / PasoFinanciero.jsx).
    """
    moneda = (datos.get("moneda_declaracion") or "").strip().upper()
    moneda_otra = datos.get("moneda_declaracion_otra")

    # Si el usuario declaró una moneda personalizada, se muestra el nombre
    # especificado en lugar del sentinel 'OTRA' (sin significado para el lector).
    moneda_mostrada = datos.get("moneda_declaracion_otra") if moneda == "OTRA" else moneda

    # Campos no monetarios (se muestran tal cual)
    pares_escalares: List[Tuple[str, Any]] = [
        ("Moneda de Declaración",         moneda_mostrada),
        ("Actividad Económica Principal", datos.get("actividad_economica")),
        ("Código CIIU",                   datos.get("codigo_ciiu")),
    ]

    # Campos monetarios formateados con la moneda correcta
    pares_montos: List[Tuple[str, Any]] = [
        (etiqueta, _formatear_monto(datos.get(clave), moneda, moneda_otra))
        for etiqueta, clave in _CAMPOS_FINANCIEROS
    ]

    return _render_seccion_campos(
        "Información Financiera",
        pares_escalares + pares_montos,
    )


def _renderizar_seccion_declaraciones(datos: Dict[str, Any]) -> str:
    texto_autorizacion = (
        "En cumplimiento de la Ley Estatutaria 1581 de 2012 de Protección de Datos (LEPD), "
        "del Decreto 1377 de 2013 y de las medidas de seguridad definidas en la política de "
        f"tratamiento desarrollada por {_RAZON_SOCIAL_EMPRESA}, a las cuales puede tener acceso "
        f"a través del correo electrónico: {_CORREO_DATOS_PERSONALES}. Mediante el registro de "
        "sus datos personales en el presente formulario usted autoriza a "
        f"{_RAZON_SOCIAL_EMPRESA} para la recolección, almacenamiento y uso de los mismos con la "
        "finalidad de llevar a cabo el procedimiento de conocimiento del cliente/proveedor de la "
        "empresa. Usted, como titular de sus datos personales puede ejercer sus derechos de acceso, "
        "corrección, supresión o revocación mediante un escrito dirigido a "
        f"{_RAZON_SOCIAL_EMPRESA}, mediante correo electrónico a {_CORREO_DATOS_PERSONALES} "
        "indicando en el asunto el derecho que desea ejercitar."
    )
    texto_origen = (
        "Manifiesto que todo lo aquí consignado es veraz. Así mismo, realizo la siguiente "
        "declaración de origen de fondos con el propósito de contribuir en la prevención y "
        "control del Lavado de Activos y Financiación del Terrorismo."
    )
    declaracion_items = [
        "Declaro que los recursos con los cuales esta sociedad fue constituida no provienen de "
        "ninguna actividad ilícita de las contempladas en el Código Penal Colombiano o en cualquier "
        "norma que lo modifique o adiciones.",
        "No admitiré que terceros efectúen depósitos a mis cuentas con fondos de actividades "
        "ilícitas contempladas en el Código Penal Colombiano o en cualquier norma que lo modifique "
        "o adicione, ni efectuaré transacciones a tales actividades de o a favor de personas "
        "relacionadas con las mismas.",
    ]
    bloques = [
        _fila_etiqueta_valor("Autorización tratamiento de datos", datos.get("autorizacion_datos")),
        _fila_etiqueta_valor("Declaración origen de fondos", datos.get("declaracion_origen_fondos")),
        _fila_etiqueta_valor("Origen de fondos (detalle)", datos.get("origen_fondos")),
    ]
    bloques = [bloque for bloque in bloques if bloque]
    items_html = "".join(f"<li>{escape(item)}</li>" for item in declaracion_items)

    return (
        "<section class='card'>"
        "<h2>Autorizaciones y Origen de Fondos</h2>"
        f"<p style='font-size:11px; color:var(--gray-800); line-height:1.7;'>{escape(texto_autorizacion)}</p>"
        f"<p style='font-size:11px; color:var(--gray-800); line-height:1.7; margin-top:14px;'>{escape(texto_origen)}</p>"
        "<ol style='margin:8px 0 14px 20px; padding:0; color:var(--gray-800); font-size:11px; line-height:1.7;'>"
        f"{items_html}"
        "</ol>"
        "<div class='grid'>"
        f"{''.join(bloques)}"
        "</div>"
        "</section>"
    )


def _renderizar_seccion(seccion: _SeccionFormulario, datos: Dict[str, Any]) -> str:
    if isinstance(seccion, _SeccionNarrativaFirma):
        return _render_narrativa_firma(seccion.titulo, datos)
    if isinstance(seccion, _SeccionCampos):
        # La sección financiera tiene tratamiento especial: usa formateo por moneda.
        if seccion.titulo == "Información Financiera":
            return _renderizar_seccion_financiera(datos)
        if seccion.titulo == "Autorizaciones y Origen de Fondos":
            return _renderizar_seccion_declaraciones(datos)
        return _render_seccion_campos(
            seccion.titulo,
            [(etiqueta, datos.get(clave)) for etiqueta, clave in seccion.campos],
        )
    filas = datos.get(seccion.clave_dato) or []
    if seccion.transformar:
        filas = seccion.transformar(filas)
    return _render_tabla(seccion.titulo, filas, seccion.columnas)


def _construir_html_formulario(datos: Dict[str, Any]) -> str:
    codigo = _valor_a_texto(datos.get("codigo_peticion")) or _valor_a_texto(datos.get("id"))
    ahora = datetime.now(timezone.utc).astimezone()

    cabecera = (
        "<div class='header'>"
        f"<div class='chip'>{escape(codigo)}</div>"
        "<h1>Formulario SAGRILAFT — Radicación</h1>"
        "<h2> FORMULARIO DE VINCULACIÓN O ACTUALIZACIÓN DE CONTRAPARTE</h2>"
        f"<div class='sub'>Versión imprimible • Generado: {escape(ahora.strftime('%Y-%m-%d %H:%M %Z'))}</div>"
        "</div>"
    )
    pie = (
        "<div class='footer'>"
        "Este documento es una representación imprimible del formulario registrado en el sistema."
        "</div>"
    )
    bloques_pasos: List[str] = []
    for paso in _PASOS_FORMULARIO:
        secciones_html = [
            html for s in paso.secciones
            if (html := _renderizar_seccion(s, datos))
        ]
        if not secciones_html:
            continue
        clase = "paso-primero" if not bloques_pasos else "paso"
        bloque = (
            f"<div class='{clase}'>"
            f"<h3 class='paso-titulo'>Paso {paso.numero} — {escape(paso.titulo)}</h3>"
            + "\n".join(secciones_html)
            + "</div>"
        )
        bloques_pasos.append(bloque)
    contenido = "\n".join(p for p in [cabecera, *bloques_pasos, pie] if p)
    return (
        f"<!doctype html><html>"
        f"<head><meta charset='utf-8'><style>{_CSS_BASE}</style></head>"
        f"<body><div class='content'>{contenido}</div></body>"
        f"</html>"
    )


# ─── Exportador (infraestructura / IO) ───────────────────────────────────────

class ExportadorFormularioPdf:
    """Convierte un formulario a PDF y devuelve los bytes — sin responsabilidad de almacenamiento."""

    def generar_bytes_pdf(
        self,
        formulario: FormularioDatos,
        numero_version: int = 1,
    ) -> tuple[str, bytes]:
        """
        Genera el PDF del formulario y devuelve (nombre_archivo, bytes).

        El nombre incluye la versión para que cada envío o corrección produzca
        un archivo único en storage — nunca sobreescribe versiones anteriores.
        Ej: FORMULARIO_SAG-CLT00042_v1.pdf, FORMULARIO_SAG-CLT00042_v2.pdf

        El llamador decide dónde guardar los bytes (local o S3).
        """
        datos = deserializar_campos_json(formulario)
        codigo = _valor_a_texto(datos.get("codigo_peticion")) or formulario.id
        nombre_archivo = f"FORMULARIO_{codigo}_v{numero_version}.pdf"
        html = _construir_html_formulario(datos)
        return nombre_archivo, self._html_a_pdf_bytes(html)

    @staticmethod
    def _html_a_pdf_bytes(html: str) -> bytes:
        try:
            from weasyprint import HTML  # type: ignore
        except Exception as exc:
            raise DependenciaPdfNoInstaladaError(
                "No se encontró 'weasyprint'. Instala dependencias del backend para habilitar exportación PDF."
            ) from exc
        return HTML(string=html).write_pdf()
