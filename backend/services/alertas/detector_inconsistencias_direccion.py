"""
Detector de inconsistencias en la dirección entre formulario y documentos adjuntos.

Instancia de DetectorInconsistencias configurada para el campo dirección.

Documentos monitoreados y ubicación del campo:
  - certificado_existencia → Dirección del domicilio principal
  - rut                    → campo 41. Dirección principal

OCP: soportar un nuevo documento = agregar una entrada en _DOCUMENTOS_MONITOREADOS.
DRY: la lógica de detección vive en DetectorInconsistencias; este módulo solo
     declara la configuración específica del campo dirección.
"""

from __future__ import annotations

from typing import Dict

from services.alertas.detector_inconsistencias import DetectorInconsistencias
from services.alertas.normalizador_direccion import normalizar_direccion


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistencias.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_direccion":    "direccion",
        "nombre_legible":     "Certificado de Existencia y Representación Legal",
        "seccion_referencia": "Dirección del domicilio principal",
    },
    "rut": {
        "campo_direccion":    "direccion",
        "nombre_legible":     "RUT (Registro Único Tributario)",
        "seccion_referencia": "Sección UBICACIÓN → campo 41. Dirección principal",
    },
}

# ── Instancia pública ─────────────────────────────────────────────────────────

detector = DetectorInconsistencias(
    normalizador=normalizar_direccion,
    documentos_monitoreados=_DOCUMENTOS_MONITOREADOS,
    campo_clave="campo_direccion",
    plantilla_mensaje=(
        'La dirección en el formulario ("{valor_formulario}") '
        'no coincide con la encontrada en {nombre_legible} ("{valor_documento}").'
    ),
)
