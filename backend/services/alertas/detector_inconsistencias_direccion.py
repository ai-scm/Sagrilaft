"""
Detector de inconsistencias en la dirección entre formulario y documentos adjuntos.

Sabe exactamente en qué campo de cada tipo de documento reside la dirección
principal, y genera una AlertaInconsistenciaDireccion cuando el valor extraído
no coincide con el campo direccion del formulario.

Documentos monitoreados y ubicación del campo:
  - certificado_existencia → Dirección del domicilio principal
                             (campo extraído: direccion)
  - rut                    → campo 41. Dirección principal
                             (campo extraído: direccion)

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si la dirección
                             de un documento es inconsistente con el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de documento = agregar una
                             entrada en _DOCUMENTOS_MONITOREADOS, sin tocar la
                             lógica de DetectorInconsistenciasDireccion.
- D (Inversión de Dependencias): depende de Comparador (abstracción),
                                 no de lógica de normalización directa.

DRY: la configuración de cada documento vive en _DOCUMENTOS_MONITOREADOS como
     única fuente de verdad. La normalización está en normalizador_direccion.py
     y es compartida con Comparador.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.alertas.comparador import Comparador
from services.alertas.normalizador_direccion import normalizar_direccion
from services.contracts import AlertaInconsistencia


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistenciasDireccion.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_direccion":   "direccion",
        "nombre_legible":    "Certificado de Existencia y Representación Legal",
        "seccion_referencia": "Dirección del domicilio principal",
    },
    "rut": {
        "campo_direccion":   "direccion",
        "nombre_legible":    "RUT (Registro Único Tributario)",
        "seccion_referencia": "Sección UBICACIÓN → campo 41. Dirección principal",
    },
}


# ── Detector ─────────────────────────────────────────────────────────────────

class DetectorInconsistenciasDireccion:
    """
    Genera alertas cuando la dirección extraída de un documento no coincide con
    la dirección registrada en el formulario.

    Uso típico (dentro de FormularioService, tras la extracción IA):
        alerta = detector.detectar(
            tipo_documento, datos_extraidos, direccion_formulario
        )

    SRP: única responsabilidad — producir o descartar una alerta de dirección.
    DIP: depende de Comparador; el comparador puede sustituirse sin
         modificar esta clase.
    """

    def __init__(self) -> None:
        self._comparador = Comparador(normalizar_direccion)

    # ── API pública ───────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        direccion_formulario: Optional[str],
    ) -> Optional[AlertaInconsistencia]:
        """
        Detecta si hay inconsistencia de dirección para el documento recién procesado.

        Args:
            tipo_documento:      Tipo del documento subido.
            datos_extraidos:     Campos crudos extraídos por IA.
            direccion_formulario: Dirección actual del formulario (puede ser None
                                  si aún no se ha diligenciado).

        Returns:
            AlertaInconsistenciaDireccion si hay discrepancia, None si coinciden
            o si no hay datos suficientes para comparar.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config["campo_direccion"])
        resultado = self._comparador.comparar(direccion_formulario, valor_documento)

        if resultado is None or resultado.coincide:
            return None

        return AlertaInconsistencia(
            tipo_documento=tipo_documento,
            nombre_documento=config["nombre_legible"],
            seccion_referencia=config["seccion_referencia"],
            valor_formulario=resultado.valor_formulario_original,
            valor_documento=resultado.valor_documento_original,
            tipo_alerta="error",
            mensaje=(
                f"La dirección en el formulario "
                f"(\"{resultado.valor_formulario_original}\") "
                f"no coincide con la encontrada en {config['nombre_legible']} "
                f"(\"{resultado.valor_documento_original}\")."
            ),
        )

    def extraer_direccion_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae la dirección de un documento sin comparar.

        Usado para devolver direccion_extraida al frontend, que la almacena
        para recomparar en tiempo real cuando el usuario edita el campo.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo de dirección, o None si no aplica o no se extrajo.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config["campo_direccion"]) or None

    @staticmethod
    def tipos_monitoreados() -> List[str]:
        """Retorna los tipos de documento que generan alertas de dirección."""
        return list(_DOCUMENTOS_MONITOREADOS.keys())
