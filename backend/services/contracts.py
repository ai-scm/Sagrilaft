"""
Contratos (Protocolos) y tipos de datos compartidos.
Definen las interfaces que deben cumplir extractores y validadores.

SOLID:
- I (Segregación de Interfaces): Protocolos pequeños y enfocados.
- D (Inversión de Dependencias): El código depende de estos protocolos,
  no de implementaciones concretas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ═══════════════════════════════════════════════════════════════
# Objetos de Valor (Value Objects)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ResultadoExtraccion:
    """
    Resultado de la extracción IA de un documento.

    Attributes:
        extraido:   True si la extracción fue exitosa.
        datos:      Campos estructurados extraídos del documento.
        mensaje:    Descripción del resultado o del error ocurrido.
        confianza:  Nivel de confianza de la extracción (0.0 a 1.0).
    """
    extraido: bool
    datos: Dict[str, Any] = field(default_factory=dict)
    mensaje: str = ""
    confianza: float = 0.0


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


# ═══════════════════════════════════════════════════════════════
# Protocolos (Interfaces)
# ═══════════════════════════════════════════════════════════════

@runtime_checkable
class IExtractorIA(Protocol):
    """
    Interfaz para la extracción de datos desde documentos usando IA.

    Implementaciones:
        - ExtractorBedrock: AWS Bedrock / Claude.
    """

    async def extraer(
        self,
        ruta_archivo: str,
        tipo_documento: str,
    ) -> ResultadoExtraccion:
        """Extrae datos estructurados de un archivo usando IA."""
        ...


@runtime_checkable
class IValidadorDocumento(Protocol):
    """
    Interfaz para validadores de documentos específicos.

    Cada tipo de documento (Cámara de Comercio, RUT, etc.) tiene
    su propio validador que implementa este Protocolo.

    SOLID - S: Cada validador tiene una única responsabilidad.
    SOLID - L: Los subtipos son intercambiables sin romper el orquestador.
    """

    @property
    def tipo_documento(self) -> str:
        """Tipo de documento que valida (ej: 'certificado_existencia')."""
        ...

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """Compara datos extraídos del documento contra datos del formulario."""
        ...


@runtime_checkable
class IValidadorCruzado(Protocol):
    """
    Interfaz para la validación de consistencia entre documentos.

    SOLID - S: Responsabilidad única: verificar coherencia entre documentos.
    SOLID - I: Interfaz mínima y enfocada, separada de IValidadorDocumento.
    SOLID - D: El orquestador depende de esta abstracción, no de implementaciones.
    """

    def validar_cruzado(
        self,
        extracciones: Dict[str, Dict[str, Any]],
    ) -> List[HallazgoValidacion]:
        """Verifica la consistencia de datos entre los documentos adjuntos."""
        ...
