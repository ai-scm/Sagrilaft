"""
Detector de inconsistencias en el número de documento del representante legal
entre el formulario y los documentos adjuntos.

Instancia de DetectorInconsistencias configurada para el campo número de
documento del representante legal.

Documentos monitoreados y ubicación del campo:
  - cedula_representante    → Número del documento de identidad del titular
  - certificado_existencia  → NOMBRAMIENTOS > REPRESENTANTES LEGALES > IDENTIFICACIÓN
  - rut                     → Representación > 101. Número de identificación
  - estados_financieros     → Número de documento del representante legal o firmante

OCP: soportar un nuevo documento = agregar una entrada en _DOCUMENTOS_MONITOREADOS.
DRY: la lógica de detección vive en DetectorInconsistencias; este módulo solo
     declara la configuración específica del campo número de documento.
"""

from __future__ import annotations

from typing import Dict

from services.alertas.detector_inconsistencias import DetectorInconsistencias
from services.alertas.normalizador_numero_doc import normalizar_numero_doc


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistencias.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "cedula_representante": {
        "campo_numero_doc":   "numero_documento",
        "nombre_legible":     "Cédula del Representante Legal",
        "seccion_referencia": "Número del documento de identidad del titular",
    },
    "certificado_existencia": {
        "campo_numero_doc":   "cedula_representante",
        "nombre_legible":     "Certificado de Existencia y Representación Legal",
        "seccion_referencia": "NOMBRAMIENTOS → REPRESENTANTES LEGALES → IDENTIFICACIÓN",
    },
    "rut": {
        "campo_numero_doc":   "cedula_representante",
        "nombre_legible":     "RUT (Registro Único Tributario)",
        "seccion_referencia": "Representación → 101. Número de identificación",
    },
    "estados_financieros": {
        "campo_numero_doc":   "cedula_representante",
        "nombre_legible":     "Estados Financieros",
        "seccion_referencia": (
            "Número de documento del representante legal o firmante del documento"
        ),
    },
}

# ── Instancia pública ─────────────────────────────────────────────────────────

detector = DetectorInconsistencias(
    normalizador=normalizar_numero_doc,
    documentos_monitoreados=_DOCUMENTOS_MONITOREADOS,
    campo_clave="campo_numero_doc",
    plantilla_mensaje=(
        'El No. de Identificación del representante en el formulario ("{valor_formulario}") '
        'no coincide con el encontrado en {nombre_legible} ("{valor_documento}").'
    ),
)
