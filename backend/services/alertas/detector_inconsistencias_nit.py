"""
Detector de inconsistencias en NIT entre formulario y documentos.

Instancia de DetectorInconsistencias configurada para el campo NIT.
Solo genera alertas cuando el tipo de identificación del formulario es "NIT";
si la contraparte usa cédula u otro tipo, no se emiten alertas.

OCP: soportar un nuevo documento = agregar una entrada en _DOCUMENTOS_MONITOREADOS.
DRY: la lógica de detección vive en DetectorInconsistencias; este módulo solo
     declara la configuración específica del campo NIT y la condición de activación.
"""

from __future__ import annotations

from typing import Any, Dict

from services.alertas.detector_inconsistencias import DetectorInconsistencias
from services.alertas.normalizador_nit import normalizar_nit


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistencias.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_nit":          "nit",
        "nombre_legible":     "Certificado de Existencia y Representación Legal",
        "seccion_referencia": "NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Nit",
    },
    "rut": {
        "campo_nit":          "nit",
        "nombre_legible":     "RUT (Registro Único Tributario)",
        "seccion_referencia": (
            "IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)"
        ),
    },
    "estados_financieros": {
        "campo_nit":          "nit",
        "nombre_legible":     "Estados Financieros",
        "seccion_referencia": "Encabezado o membrete del documento (NIT del emisor)",
    },
    "declaracion_renta": {
        "campo_nit":          "nit",
        "nombre_legible":     "Declaración de Renta",
        "seccion_referencia": (
            "IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)"
        ),
    },
    "referencias_bancarias": {
        "campo_nit":          "nit",
        "nombre_legible":     "Referencias Bancarias",
        "seccion_referencia": (
            "NIT del titular de la cuenta (si aparece en el documento)"
        ),
    },
}


def _solo_si_es_nit(tipo_identificacion_formulario: Any = "", **_: Any) -> bool:
    """Activa el detector únicamente cuando la contraparte tiene NIT."""
    return (tipo_identificacion_formulario or "").upper() == "NIT"


# ── Instancia pública ─────────────────────────────────────────────────────────

detector = DetectorInconsistencias(
    normalizador=normalizar_nit,
    documentos_monitoreados=_DOCUMENTOS_MONITOREADOS,
    campo_clave="campo_nit",
    plantilla_mensaje=(
        'El NIT en el formulario ("{valor_formulario}") '
        'no coincide con el encontrado en {nombre_legible} ("{valor_documento}").'
    ),
    condicion_previa=_solo_si_es_nit,
)
