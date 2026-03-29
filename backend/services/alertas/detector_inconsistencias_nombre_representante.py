"""
Detector de inconsistencias en nombre del representante legal entre formulario
y documentos adjuntos.

Sabe exactamente en qué campo de cada tipo de documento reside el nombre del
representante legal y genera una AlertaInconsistenciaNombreRepresentante cuando
el valor extraído no coincide con el campo nombre_representante del formulario.

Reutiliza ComparadorRazonSocial porque la tolerancia que ya implementa
(diacríticos, mayúsculas, espacios) es exactamente la que se necesita para
comparar nombres de personas. Las sustituciones de siglas societarias (SAS,
LTDA…) no causan falsos negativos en nombres personales porque no aparecen
en ellos.

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si el nombre
                             del representante de un documento es inconsistente
                             con el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de documento = agregar una
                             entrada en _DOCUMENTOS_MONITOREADOS, sin tocar
                             la lógica de DetectorInconsistenciasNombreRepresentante.
- D (Inversión de Dependencias): depende de ComparadorRazonSocial (abstracción
                                 ya probada), no reimplementa lógica de comparación.

DRY: reutiliza ComparadorRazonSocial en lugar de duplicar la normalización.
     La configuración de cada documento vive en _DOCUMENTOS_MONITOREADOS como
     única fuente de verdad.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.alertas.comparador_razon_social import ComparadorRazonSocial
from services.contracts import AlertaInconsistencia


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No tocar DetectorInconsistenciasNombreRepresentante.

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


# ── Detector ─────────────────────────────────────────────────────────────────

class DetectorInconsistenciasNombreRepresentante:
    """
    Genera alertas cuando el nombre del representante legal extraído de un
    documento no coincide con el ingresado en el formulario.

    Reutiliza ComparadorRazonSocial para la comparación tolerante: la
    normalización (quitar tildes, mayúsculas, colapsar espacios) es aplicable
    tanto a razones sociales como a nombres de personas.

    Uso típico (dentro de FormularioService, tras la extracción IA):
        alerta = detector.detectar(
            tipo_documento, datos_extraidos, nombre_representante_form
        )

    SRP: única responsabilidad — producir o descartar una alerta de nombre
         de representante.
    DIP: depende de ComparadorRazonSocial; el comparador puede sustituirse sin
         modificar esta clase.
    """

    def __init__(self) -> None:
        self._comparador = ComparadorRazonSocial()

    # ── API pública ───────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        nombre_representante_formulario: Optional[str],
    ) -> Optional[AlertaInconsistencia]:
        """
        Detecta si hay inconsistencia de nombre de representante para el documento
        recién procesado.

        Args:
            tipo_documento:                  Tipo del documento subido.
            datos_extraidos:                 Campos crudos extraídos por IA.
            nombre_representante_formulario: Nombre del representante legal actual
                                             del formulario (puede ser None si aún
                                             no se ha diligenciado).

        Returns:
            AlertaInconsistenciaNombreRepresentante si hay discrepancia, None si
            coinciden o si no hay datos suficientes para comparar.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config["campo_nombre"])
        resultado = self._comparador.comparar(
            nombre_representante_formulario, valor_documento
        )

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
                f"El nombre del representante en el formulario "
                f"(\"{resultado.valor_formulario_original}\") "
                f"no coincide con el encontrado en {config['nombre_legible']} "
                f"(\"{resultado.valor_documento_original}\")."
            ),
        )

    def extraer_nombre_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae el nombre del representante legal de un documento sin comparar.

        Usado para devolver nombre_representante_extraido al frontend, que lo
        almacena para recomparar en tiempo real cuando el usuario edita el campo.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo de nombre del representante, o None si no aplica
            o no se extrajo.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config["campo_nombre"]) or None

    @staticmethod
    def tipos_monitoreados() -> List[str]:
        """Retorna los tipos de documento que generan alertas de nombre de representante."""
        return list(_DOCUMENTOS_MONITOREADOS.keys())
