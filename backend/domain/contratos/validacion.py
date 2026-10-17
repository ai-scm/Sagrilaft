"""
Value Objects de validación documental y comparación de campos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HallazgoValidacion:
    """
    Un hallazgo individual de validación documental.

    Attributes:
        resultado:         Nivel del hallazgo: "ok", "error" o "advertencia".
        campo:             Campo del formulario al que aplica.
        detalle:           Descripción legible del hallazgo.
        valor_formulario:  Valor ingresado por el usuario (si aplica).
        valor_documento:   Valor extraído del documento (si aplica).
    """
    resultado: str          # "ok" | "error" | "advertencia"
    campo: str
    detalle: str
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None

    # ── Métodos de fábrica ── evitan repetir resultado="ok"|"error"|"advertencia" ──

    @classmethod
    def ok(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("ok", campo, detalle, valor_formulario, valor_documento)

    @classmethod
    def error(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("error", campo, detalle, valor_formulario, valor_documento)

    @classmethod
    def advertencia(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("advertencia", campo, detalle, valor_formulario, valor_documento)


@dataclass(frozen=True)
class ResultadoComparacion:
    """
    Resultado de comparar un campo del formulario contra el extraído de un documento.

    Value Object inmutable y genérico que reemplaza los cuatro dataclasses específicos
    anteriores (ResultadoComparacion, ResultadoComparacionNit, ResultadoComparacionNumeroDoc,
    ResultadoComparacionDireccion). Todos tenían los mismos cinco campos.

    OCP: agregar un nuevo tipo de comparación no requiere crear otro dataclass,
         solo instanciar Comparador con el normalizador correspondiente.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


@dataclass(frozen=True)
class AlertaInconsistencia:
    """
    Inconsistencia detectada entre un campo del formulario y un documento adjunto.

    Value Object inmutable y unificado para todos los tipos de alerta de campo.
    Reemplaza las 5 clases específicas anteriores (AlertaInconsistenciaNombre,
    AlertaInconsistenciaNit, etc.) con un único modelo agnóstico del campo.

    Lenguaje ubicuo:
        - tipo_documento:     clave del tipo de documento (ej. "certificado_existencia").
        - nombre_documento:   nombre legible del documento para mostrar al usuario.
        - seccion_referencia: ubicación exacta del campo dentro del documento.
        - valor_formulario:   valor ingresado por el usuario en el formulario.
        - valor_documento:    valor extraído del documento por la IA.
        - tipo_alerta:        gravedad: "error" | "advertencia".
        - mensaje:            descripción legible para el usuario final.

    OCP: agregar un nuevo tipo de alerta no requiere crear una nueva clase,
         solo instanciar AlertaInconsistencia con los valores correspondientes.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str   # "error" | "advertencia"
    mensaje: str
