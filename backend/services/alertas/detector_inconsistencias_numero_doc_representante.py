"""
Detector de inconsistencias en el número de documento del representante legal
entre el formulario y los documentos adjuntos.

Sabe exactamente en qué campo de cada tipo de documento reside el número de
identificación del representante y genera una
AlertaInconsistenciaNumeroDocRepresentante cuando el valor extraído no coincide
con el campo numero_doc_representante del formulario.

Documentos monitoreados y ubicación del campo:
  - certificado_existencia → NOMBRAMIENTOS > REPRESENTANTES LEGALES > IDENTIFICACIÓN
                             (campo extraído: cedula_representante)
  - rut                    → Representación > 101. Número de identificación
                             (campo extraído: cedula_representante)
  - estados_financieros    → Número de documento del representante legal o firmante
                             (campo extraído: cedula_representante)

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si el número de
                             documento del representante de un documento es
                             inconsistente con el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de documento = agregar una
                             entrada en _DOCUMENTOS_MONITOREADOS, sin tocar la
                             lógica de DetectorInconsistenciasNumeroDocRepresentante.
- D (Inversión de Dependencias): depende de ComparadorNumeroDoc (abstracción),
                                 no de lógica de normalización directa.

DRY: la configuración de cada documento vive en _DOCUMENTOS_MONITOREADOS como
     única fuente de verdad. La normalización está en normalizador_numero_doc.py
     y es compartida con ComparadorNumeroDoc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.alertas.comparador_numero_doc import ComparadorNumeroDoc


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar el detector.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "cedula_representante": {
        "campo_numero_doc":  "numero_documento",
        "nombre_legible":    "Cédula del Representante Legal",
        "seccion_referencia": "Número del documento de identidad del titular",
    },
    "certificado_existencia": {
        "campo_numero_doc":  "cedula_representante",
        "nombre_legible":    "Certificado de Existencia y Representación Legal",
        "seccion_referencia": (
            "NOMBRAMIENTOS → REPRESENTANTES LEGALES → IDENTIFICACIÓN"
        ),
    },
    "rut": {
        "campo_numero_doc":  "cedula_representante",
        "nombre_legible":    "RUT (Registro Único Tributario)",
        "seccion_referencia": (
            "Representación → 101. Número de identificación"
        ),
    },
    "estados_financieros": {
        "campo_numero_doc":  "cedula_representante",
        "nombre_legible":    "Estados Financieros",
        "seccion_referencia": (
            "Número de documento del representante legal o firmante del documento"
        ),
    },
}


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class AlertaInconsistenciaNumeroDocRepresentante:
    """
    Inconsistencia detectada entre el número de documento del representante en
    el formulario y el encontrado en un documento adjunto.

    Immutable Value Object: no puede modificarse una vez creado.

    Attributes:
        tipo_documento:    Clave del tipo (ej. "certificado_existencia").
        nombre_documento:  Nombre legible del documento.
        seccion_referencia: Ubicación exacta del campo dentro del documento.
        valor_formulario:  Número de documento tal como aparece en el formulario.
        valor_documento:   Número tal como fue extraído del documento.
        tipo_alerta:       Gravedad: "error".
        mensaje:           Descripción legible para el usuario final.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str   # "error"
    mensaje: str


# ── Detector ─────────────────────────────────────────────────────────────────

class DetectorInconsistenciasNumeroDocRepresentante:
    """
    Genera alertas cuando el número de documento del representante legal
    extraído de un documento no coincide con el ingresado en el formulario.

    Uso típico (dentro de FormularioService, tras la extracción IA):
        alerta = detector.detectar(
            tipo_documento, datos_extraidos, numero_doc_representante_form
        )

    SRP: única responsabilidad — producir o descartar una alerta de número de
         documento del representante.
    DIP: depende de ComparadorNumeroDoc; el comparador puede sustituirse sin
         modificar esta clase.
    """

    def __init__(self) -> None:
        self._comparador = ComparadorNumeroDoc()

    # ── API pública ───────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        numero_doc_representante_formulario: Optional[str],
    ) -> Optional[AlertaInconsistenciaNumeroDocRepresentante]:
        """
        Detecta si hay inconsistencia de número de documento del representante
        para el documento recién procesado.

        Args:
            tipo_documento:                      Tipo del documento subido.
            datos_extraidos:                     Campos crudos extraídos por IA.
            numero_doc_representante_formulario: Número de documento del representante
                                                 actual del formulario (puede ser None
                                                 si aún no se ha diligenciado).

        Returns:
            AlertaInconsistenciaNumeroDocRepresentante si hay discrepancia, None si
            coinciden o si no hay datos suficientes para comparar.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config["campo_numero_doc"])
        resultado = self._comparador.comparar(
            numero_doc_representante_formulario, valor_documento
        )

        if resultado is None or resultado.coincide:
            return None

        return AlertaInconsistenciaNumeroDocRepresentante(
            tipo_documento=tipo_documento,
            nombre_documento=config["nombre_legible"],
            seccion_referencia=config["seccion_referencia"],
            valor_formulario=resultado.valor_formulario_original,
            valor_documento=resultado.valor_documento_original,
            tipo_alerta="error",
            mensaje=(
                f"El No. de Identificación del representante en el formulario "
                f"(\"{resultado.valor_formulario_original}\") "
                f"no coincide con el encontrado en {config['nombre_legible']} "
                f"(\"{resultado.valor_documento_original}\")."
            ),
        )

    def extraer_numero_doc_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae el número de documento del representante de un documento sin comparar.

        Usado para devolver numero_doc_representante_extraido al frontend, que lo
        almacena para recomparar en tiempo real cuando el usuario edita el campo.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo de número de documento, o None si no aplica o no
            se extrajo.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config["campo_numero_doc"]) or None

    @staticmethod
    def tipos_monitoreados() -> List[str]:
        """Retorna los tipos de documento que generan alertas de número de documento."""
        return list(_DOCUMENTOS_MONITOREADOS.keys())
