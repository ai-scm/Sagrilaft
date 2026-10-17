"""
Puerto para la extracción de datos desde documentos usando IA.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.contratos.documentos import ResultadoExtraccion


@runtime_checkable
class ExtractorIAImp(Protocol):
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
