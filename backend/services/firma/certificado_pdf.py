"""
Generación del Certificado de Terceros SAGRILAFT — HIGHTECH SOFTWARE S.A.S.

Replica fielmente el documento PDF entregado como plantilla. Los campos
dinámicos (nombre, documento, razón social, NIT, fecha) se toman del
formulario de la contraparte. El tag {{S:R1*...}} embebido en la sección
de firma permite que ZohoSign coloque el campo de firma en ese lugar.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from domain.utils.fechas import NOMBRES_MESES_ES
from infrastructure.persistencia.models import Formulario

logger = logging.getLogger(__name__)

# Relleno de espacios para que ZohoSign detecte el campo de firma.
# Mismo tag que el formulario (R1 = mismo firmante, misma acción).
_TAG_FIRMA = "{{S:R1*" + " " * 100 + "}}"

_SIGLAS_DOC = {
    "CC":        "C.C.",
    "CE":        "C.E.",
    "NIT":       "NIT",
    "PASAPORTE": "Pasaporte",
    "TI":        "T.I.",
    "PEP":       "P.E.P.",
}


def generar_certificado_pdf(formulario: Formulario, output_path: Path) -> Path:
    """
    Genera el Certificado de Terceros SAGRILAFT como PDF y lo guarda en output_path.

    Los datos del representante y de la empresa se extraen del formulario.
    La fecha se toma de los campos dia/mes/year_firma; si no existen, se usa
    la fecha actual.

    Returns:
        output_path — misma ruta recibida, para encadenamiento.
    """
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError(
            "WeasyPrint no está instalado. Ejecuta: pip install weasyprint"
        ) from exc

    html = _render_certificado(formulario)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(output_path))

    logger.info("Certificado SAGRILAFT generado: %s", output_path)
    return output_path


# ─── Renderizado HTML ──────────────────────────────────────────────────────────

def _render_certificado(formulario: Formulario) -> str:
    ahora = datetime.now(timezone.utc)

    nombre_repr = formulario.nombre_representante or "___________________"
    tipo_doc    = _SIGLAS_DOC.get(
        (formulario.tipo_doc_representante or "").upper(),
        formulario.tipo_doc_representante or "C.C."
    )
    numero_doc  = formulario.numero_doc_representante or "___________________"
    razon_social = formulario.razon_social or "___________________"

    # NIT: número + dígito de verificación si existe
    nit_numero = formulario.numero_identificacion or "___________________"
    nit_dv     = formulario.digito_verificacion
    nit_str    = f"{nit_numero}-{nit_dv}"

    dia    = formulario.dia_firma  or ahora.day
    mes    = formulario.mes_firma  or ahora.month
    year   = formulario.year_firma or ahora.year
    ciudad = formulario.ciudad_firma or "Bogotá D.C."

    fecha_str = f"{dia} de {NOMBRES_MESES_ES[mes - 1]} de {year}"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<style>
  @page {{
    size: A4;
    margin: 2.8cm 3cm 2.5cm 3cm;
  }}
  body {{
    font-family: "Times New Roman", Georgia, Times, serif;
    font-size: 11.5pt;
    color: #000;
    line-height: 1.55;
  }}
  .titulo {{
    text-align: center;
    font-weight: bold;
    font-size: 12pt;
    margin-bottom: 2em;
  }}
  .intro {{
    text-align: justify;
    margin-bottom: 1.6em;
  }}
  .seccion {{
    margin-bottom: 1.2em;
  }}
  .seccion-titulo {{
    font-weight: bold;
    display: block;
    margin-bottom: 0.3em;
  }}
  .seccion-cuerpo {{
    text-align: justify;
  }}
  .certificacion-final {{
    text-align: justify;
    margin-top: 1.4em;
    margin-bottom: 2.5em;
  }}
  .firma-bloque {{
    margin-top: 2em;
  }}
  .firma-campo {{
    margin-bottom: 1.6em;
  }}
  .firma-etiqueta {{
    font-weight: bold;
    display: block;
    margin-bottom: 0.2em;
  }}
  .firma-linea {{
    display: block;
    border-bottom: 1px solid #000;
    width: 90%;
    min-height: 1.4em;
    padding-bottom: 0.1em;
  }}
  .firma-valor {{
    display: block;
    padding-top: 0.1em;
    font-size: 10.5pt;
    color: #000;
  }}
  .firma-tag {{
    /* Tag de ZohoSign — texto blanco, invisible al lector pero detectable por ZohoSign */
    color: white;
    font-family: monospace;
    font-size: 14pt;
    line-height: 0;
  }}
</style>
</head>
<body>

  <p class="titulo">CERTIFICACIÓN DE TERCEROS HIGHTECH SOFTWARE S.A.S.</p>

  <p class="intro">
    Yo, <strong>{nombre_repr}</strong>, identificado(a) con {tipo_doc}
    <strong>{numero_doc}</strong>, actuando en calidad de representante legal de
    <strong>{razon_social}</strong>, sociedad identificada con NIT No.
    <strong>{nit_str}</strong>, en mi calidad de potencial contraparte en proceso de
    vinculación, manifiesto bajo la gravedad de juramento lo siguiente, para todos los
    efectos del Sistema de Autocontrol y Gestión del Riesgo de Lavado de Activos,
    Financiación del Terrorismo y Financiación de la Proliferación de Armas de
    Destrucción Masiva – SAGRILAFT de HIGHTECH SOFTWARE S.A.S.:
  </p>

  <div class="seccion">
    <span class="seccion-titulo">1. DECLARACIÓN DE ACTIVIDADES LÍCITAS</span>
    <p class="seccion-cuerpo">
      Certifico que mis actividades comerciales, profesionales, financieras y económicas
      provienen exclusivamente de fuentes lícitas y no guardan relación con actividades
      que constituyan o puedan constituir delitos relacionados con LA/FT/FPADM.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">2. CUMPLIMIENTO DE POLÍTICAS SAGRILAFT</span>
    <p class="seccion-cuerpo">
      Declaro que conozco y acepto las políticas, lineamientos y controles implementados
      por HIGHTECH SOFTWARE S.A.S. en su SAGRILAFT, y me comprometo a cumplir con todas
      las obligaciones y requerimientos derivados del mismo.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">3. AUSENCIA DE VÍNCULOS CON ACTIVIDADES ILÍCITAS</span>
    <p class="seccion-cuerpo">
      Certifico que no me encuentro vinculado(a), directa o indirectamente, con
      organizaciones, personas o actividades asociadas a lavado de activos, financiación
      del terrorismo o proliferación de armas de destrucción masiva.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">4. LISTAS RESTRICTIVAS</span>
    <p class="seccion-cuerpo">
      Declaro que no aparezco incluido(a) en las siguientes listas restrictivas nacionales
      o internacionales: OFAC, ONU, UE, UK-HMT, Lista Clinton u otras listas reconocidas
      por la UIAF o autoridades competentes.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">5. SUMINISTRO DE INFORMACIÓN</span>
    <p class="seccion-cuerpo">
      Me comprometo a suministrar información completa, veraz, exacta y verificable
      cuando sea solicitada en procesos de debida diligencia, monitoreo, actualización
      o verificación.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">6. AUTORIZACIÓN PARA CONSULTA</span>
    <p class="seccion-cuerpo">
      Autorizo expresamente a HIGHTECH SOFTWARE S.A.S. a realizar consultas en listas,
      bases de datos públicas, privadas y sistemas de información con el fin de validar
      mi identidad, actividad y ausencia de vínculos con actividades ilícitas.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">7. COMPROMISO DE REPORTE</span>
    <p class="seccion-cuerpo">
      Me comprometo a informar de manera inmediata cualquier cambio relevante en mi
      información, así como cualquier hecho inusual o sospechoso que pueda implicar
      riesgo de LA/FT/FPADM dentro de la relación contractual o comercial.
    </p>
  </div>

  <div class="seccion">
    <span class="seccion-titulo">8. CONSECUENCIAS POR INCUMPLIMIENTO</span>
    <p class="seccion-cuerpo">
      Acepto que el incumplimiento de estas declaraciones podrá generar la terminación
      inmediata de la relación comercial con HIGHTECH SOFTWARE S.A.S. sin lugar a
      indemnización alguna, sin perjuicio de las acciones legales aplicables.
    </p>
  </div>

  <p class="certificacion-final">
    CERTIFICO que toda la información contenida en este documento es cierta, y autorizo
    su verificación por parte de HIGHTECH SOFTWARE S.A.S.
  </p>

  <!-- ── Sección de firma ── -->
  <div class="firma-bloque">

    <div class="firma-campo">
      <span class="firma-etiqueta">Firma del Tercero:</span>
      <span class="firma-linea">
        <span class="firma-tag">{_TAG_FIRMA}</span>
      </span>
    </div>

    <div class="firma-campo">
      <span class="firma-etiqueta">Nombre Completo:</span>
      <span class="firma-linea">
        <span class="firma-valor">{nombre_repr}</span>
      </span>
    </div>

    <div class="firma-campo">
      <span class="firma-etiqueta">Razón Social:</span>
      <span class="firma-linea">
        <span class="firma-valor">{razon_social}</span>
      </span>
    </div>

    <div class="firma-campo">
      <span class="firma-etiqueta">Cargo:</span>
      <span class="firma-valor" style="padding-left:0">Representante Legal</span>
    </div>

    <div class="firma-campo">
      <span class="firma-etiqueta">Fecha:</span>
      <span class="firma-linea">
        <span class="firma-valor">{ciudad}, {fecha_str}</span>
      </span>
    </div>

  </div>

</body>
</html>"""
