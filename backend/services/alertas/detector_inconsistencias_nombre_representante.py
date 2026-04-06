"""
Detector de inconsistencias en nombre del representante legal entre formulario
y documentos adjuntos.

Instancia de DetectorInconsistencias configurada para el campo nombre del
representante legal. Reutiliza normalizar_razon_social porque la tolerancia
que ya implementa (diacríticos, mayúsculas, espacios) es exactamente la que
se necesita para comparar nombres de personas.

OCP: soportar un nuevo documento = agregar una entrada en _DOCUMENTOS_MONITOREADOS.
DRY: la lógica de detección vive en DetectorInconsistencias; este módulo solo
     declara la configuración específica del campo nombre del representante.
"""

from __future__ import annotations

from typing import Dict

from services.alertas.detector_inconsistencias import DetectorInconsistencias
from services.alertas.normalizador_nombre import normalizar_razon_social


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No tocar DetectorInconsistencias.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_nombre":       "representante_legal",
        "nombre_legible":     "Certificado de Existencia y Representación Legal",
        "seccion_referencia": "REPRESENTANTES LEGALES → NOMBRE",
    },
    "rut": {
        "campo_nombre":       "nombre_representante",
        "nombre_legible":     "RUT (Registro Único Tributario)",
        "seccion_referencia": (
            "Representación → campos 106, 107, 104, 105 "
            "(Primer nombre, Otros nombres, Primer apellido, Segundo apellido)"
        ),
    },
    "estados_financieros": {
        "campo_nombre":       "nombre_representante",
        "nombre_legible":     "Estados Financieros",
        "seccion_referencia": "Representante legal o firmante del documento",
    },
}

# ── Instancia pública ─────────────────────────────────────────────────────────

detector = DetectorInconsistencias(
    normalizador=normalizar_razon_social,
    documentos_monitoreados=_DOCUMENTOS_MONITOREADOS,
    campo_clave="campo_nombre",
    plantilla_mensaje=(
        'El nombre del representante en el formulario ("{valor_formulario}") '
        'no coincide con el encontrado en {nombre_legible} ("{valor_documento}").'
    ),
)
