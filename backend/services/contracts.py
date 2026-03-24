"""
Contratos (Protocols) y tipos de datos compartidos.
Definen las interfaces que deben cumplir extractores y validadores.

Principio SOLID:
- I (Interface Segregation): Interfaces pequeñas y enfocadas.
- D (Dependency Inversion): El código depende de estos protocols, no de implementaciones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ═══════════════════════════════════════════════════════════════
# Value Objects
# ═══════════════════════════════════════════════════════════════

@dataclass
class ExtractionResult:
    """Resultado de la extracción IA de un documento."""
    extraido: bool
    datos: Dict[str, Any] = field(default_factory=dict)
    mensaje: str = ""
    confianza: float = 0.0  # 0.0 a 1.0


@dataclass
class ValidationFinding:
    """Un hallazgo individual de validación."""
    resultado: str          # "ok", "error", "advertencia"
    campo: str              # Campo del formulario afectado
    detalle: str            # Descripción legible del hallazgo
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Protocols (Interfaces)
# ═══════════════════════════════════════════════════════════════

@runtime_checkable
class IAIExtractor(Protocol):
    """
    Interfaz para extracción de datos desde documentos usando IA.
    
    Implementation:
        - BedrockExtractor: AWS Bedrock / Claude.
    """

    async def extract(
        self,
        file_path: str,
        document_type: str,
    ) -> ExtractionResult:
        """Extrae datos estructurados de un archivo."""
        ...


@runtime_checkable
class IDocumentValidator(Protocol):
    """
    Interfaz para validadores de documentos específicos.
    
    Cada tipo de documento (Cámara Comercio, RUT, etc.) tiene
    su propio validador que implementa este Protocol.
    
    Principio SOLID - S: Cada validador tiene una sola responsabilidad.
    """

    @property
    def document_type(self) -> str:
        """Tipo de documento que valida (ej: 'certificado_existencia')."""
        ...

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        """Compara datos extraídos del documento contra datos del formulario."""
        ...
