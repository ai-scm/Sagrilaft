"""
Detector de inconsistencias en nombre/razón social entre formulario y documentos.

Instancia de DetectorInconsistencias configurada para el campo nombre/razón social.

OCP: soportar un nuevo documento = agregar una entrada en _DOCUMENTOS_MONITOREADOS.
DRY: la lógica de detección vive en DetectorInconsistencias; este módulo solo
     declara la configuración específica del campo nombre.
"""

from __future__ import annotations

from typing import Dict

from services.alertas.detector_inconsistencias import DetectorInconsistencias
from services.alertas.normalizador_nombre import normalizar_razon_social


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistencias.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_nombre":       "razon_social",
        "nombre_legible":     "Revisa los documentos adjuntos",
        "seccion_referencia": "NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Razón social",
    },
    "rut": {
        "campo_nombre":       "razon_social",
        "nombre_legible":     "RUT (Registro Único Tributario)",
        "seccion_referencia": "IDENTIFICACIÓN → campo 35. Razón social",
    },
    "estados_financieros": {
        "campo_nombre":       "razon_social",
        "nombre_legible":     "Estados Financieros",
        "seccion_referencia": "Encabezado del documento (razón social del emisor)",
    },
    "referencias_bancarias": {
        "campo_nombre":       "titular",
        "nombre_legible":     "Referencias Bancarias",
        "seccion_referencia": "Nombre del titular de la cuenta",
    },
}

# ── Instancia pública ─────────────────────────────────────────────────────────

detector = DetectorInconsistencias(
    normalizador=normalizar_razon_social,
    documentos_monitoreados=_DOCUMENTOS_MONITOREADOS,
    campo_clave="campo_nombre",
    plantilla_mensaje=(
        'La razón social en el formulario ("{valor_formulario}") '
        'no coincide con la encontrada en {nombre_legible} ("{valor_documento}").'
    ),
)
