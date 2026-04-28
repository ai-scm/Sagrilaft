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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from infrastructure.persistencia.models import Formulario
from services.formulario.documento_service import DocumentoService
from services.formulario.serializacion import deserializar_campos_json


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
        "<section class='card'>"
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
      --primary-600:#4f46e5; --primary-700:#4338ca; --primary-800:#3730a3; --primary-900:#312e81;
      --gray-50:#f8fafc; --gray-100:#f1f5f9; --gray-200:#e2e8f0; --gray-600:#475569; --gray-800:#1e293b; --gray-900:#0f172a;
      --radius-lg:16px; --shadow-md:0 4px 6px -1px rgba(0,0,0,.10),0 2px 4px -1px rgba(0,0,0,.06);
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
      border-radius: var(--radius-lg); box-shadow: 0 4px 6px -1px rgba(0,0,0,.10),0 2px 4px -1px rgba(0,0,0,.06);
      padding:14px 16px; margin: 12px 0;
    }
    .card h2{ margin:0 0 10px 0; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--gray-600); }
    .grid{ display:grid; grid-template-columns: 1fr 1fr; gap:10px 14px; }
    .kv{ border:1px solid var(--gray-200); border-radius:12px; padding:10px 10px; background:var(--gray-50); }
    .k{ font-size:10px; color:var(--gray-600); text-transform:uppercase; letter-spacing:.05em; font-weight:700; }
    .v{ margin-top:4px; font-size:11px; font-weight:600; color:var(--gray-800); white-space:pre-wrap; }
    .table-wrap{ overflow:hidden; border-radius:12px; border:1px solid var(--gray-200); }
    table{ width:100%; border-collapse:collapse; font-size:10px; }
    thead th{ text-align:left; padding:8px 10px; background:var(--gray-50); color:var(--gray-600); text-transform:uppercase; letter-spacing:.05em; font-weight:800; border-bottom:1px solid var(--gray-200); }
    tbody td{ padding:8px 10px; border-bottom:1px solid var(--gray-200); vertical-align:top; }
    tbody tr:last-child td{ border-bottom:0; }
    .muted{ color:var(--gray-600); font-size:10px; margin-top:6px; }
    .footer{ margin-top:10px; font-size:9px; color:var(--gray-600); }
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


_SeccionFormulario = Union[_SeccionCampos, _SeccionTabla]

_SECCIONES_FORMULARIO: List[_SeccionFormulario] = [
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
        ("Ciudad (funciones)",        "ciudad_funciones"),
        ("Dirección de residencia",   "direccion_residencia"),
        ("Ciudad de residencia",      "ciudad_residencia"),
    ]),
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
    _SeccionCampos("Información Financiera", [
        ("Actividad Económica Principal", "actividad_economica"),
        ("Código CIIU",                   "codigo_ciiu"),
        ("Ingresos Mensuales (COP)",      "ingresos_mensuales"),
        ("Otros Ingresos (COP)",          "otros_ingresos"),
        ("Egresos Mensuales (COP)",       "egresos_mensuales"),
        ("Total Activos (COP)",           "total_activos"),
        ("Total Pasivos (COP)",           "total_pasivos"),
        ("Patrimonio (COP)",              "patrimonio"),
    ]),
    _SeccionTabla("Referencias Comerciales", "referencias_comerciales", [
        ("nombre_establecimiento", "Nombre del establecimiento"),
        ("persona_contacto",       "Persona a contactar"),
        ("telefono",               "Teléfono"),
        ("ciudad",                 "Ciudad"),
    ], _normalizar_referencias_comerciales),
    _SeccionTabla("Referencias Bancarias", "referencias_bancarias", [
        ("banco",         "Banco"),
        ("tipo_cuenta",   "Tipo cuenta"),
        ("numero_cuenta", "Número cuenta"),
        ("ciudad",        "Ciudad"),
    ]),
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
    _SeccionCampos("Contactos — Persona autorizada para recepción de órdenes", [
        ("Órdenes — Nombre",   "contacto_ordenes_nombre"),
        ("Órdenes — Cargo",    "contacto_ordenes_cargo"),
        ("Órdenes — Teléfono", "contacto_ordenes_telefono"),
        ("Órdenes — Correo",   "contacto_ordenes_correo"),
        ("Pagos — Nombre",     "contacto_pagos_nombre"),
        ("Pagos — Cargo",      "contacto_pagos_cargo"),
        ("Pagos — Teléfono",   "contacto_pagos_telefono"),
        ("Pagos — Correo",     "contacto_pagos_correo"),
    ]),
    _SeccionTabla("Información Bancaria para Pagos", "informacion_bancaria_pagos", [
        ("entidad_bancaria", "Banco"),
        ("ciudad_oficina",   "Ciudad oficina"),
        ("tipo_cuenta",      "Tipo cuenta"),
        ("numero_cuenta",    "Número cuenta"),
    ]),
    _SeccionCampos("Autorizaciones y Origen de Fondos", [
        ("Autorización tratamiento de datos", "autorizacion_datos"),
        ("Declaración origen de fondos",      "declaracion_origen_fondos"),
        ("Origen de fondos (detalle)",        "origen_fondos"),
    ]),
    _SeccionCampos("Firma", [
        ("Nombre", "nombre_firma"),
        ("Fecha",  "fecha_firma"),
        ("Ciudad", "ciudad_firma"),
    ]),
]


# ─── Constructor HTML ─────────────────────────────────────────────────────────

def _renderizar_seccion(seccion: _SeccionFormulario, datos: Dict[str, Any]) -> str:
    if isinstance(seccion, _SeccionCampos):
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
        f"<div class='sub'>Versión imprimible • Generado: {escape(ahora.strftime('%Y-%m-%d %H:%M %Z'))}</div>"
        "</div>"
    )
    pie = (
        "<div class='footer'>"
        "Este documento es una representación imprimible del formulario registrado en el sistema."
        "</div>"
    )
    secciones = [_renderizar_seccion(s, datos) for s in _SECCIONES_FORMULARIO]
    contenido = "\n".join(p for p in [cabecera, *secciones, pie] if p)
    return (
        f"<!doctype html><html>"
        f"<head><meta charset='utf-8'><style>{_CSS_BASE}</style></head>"
        f"<body><div class='content'>{contenido}</div></body>"
        f"</html>"
    )


# ─── Exportador (infraestructura / IO) ───────────────────────────────────────

class ExportadorFormularioPdf:
    """Convierte un formulario a PDF y lo persiste en el directorio indicado."""

    def __init__(self, documentos: DocumentoService) -> None:
        self._documentos = documentos

    def generar_y_guardar_pdf(
        self, formulario: Formulario, directorio_destino: Path
    ) -> ArchivoPdfGenerado:
        datos = deserializar_campos_json(formulario)
        codigo = _valor_a_texto(datos.get("codigo_peticion")) or formulario.id
        nombre_archivo = f"FORMULARIO_{codigo}.pdf"

        html = _construir_html_formulario(datos)
        pdf_bytes = self._html_a_pdf_bytes(html)
        ruta = self._documentos.guardar_archivo_en_disco(
            directorio_destino, nombre_archivo, pdf_bytes
        )
        return ArchivoPdfGenerado(nombre_archivo=nombre_archivo, ruta_archivo=ruta)

    @staticmethod
    def _html_a_pdf_bytes(html: str) -> bytes:
        try:
            from weasyprint import HTML  # type: ignore
        except Exception as exc:
            raise DependenciaPdfNoInstaladaError(
                "No se encontró 'weasyprint'. Instala dependencias del backend para habilitar exportación PDF."
            ) from exc
        return HTML(string=html).write_pdf()
