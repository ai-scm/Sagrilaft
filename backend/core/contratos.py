"""
Re-exporta los contratos desde domain/contratos.py para compatibilidad con imports existentes.

Los contratos (protocolos y value objects) viven en domain/contratos.py.
Este módulo re-exporta todo para que los imports existentes del tipo
`from core.contratos import ExtractorIAImp` sigan funcionando sin cambios.
"""

from domain.contratos import (  # noqa: F401
    AlertaInconsistencia,
    ExtractorIAImp,
    HallazgoValidacion,
    ResultadoComparacion,
    ResultadoExtraccion,
    ValidadorCruzadoImp,
    ValidadorDocumentoImp,
)

__all__ = [
    "AlertaInconsistencia",
    "ExtractorIAImp",
    "HallazgoValidacion",
    "ResultadoComparacion",
    "ResultadoExtraccion",
    "ValidadorCruzadoImp",
    "ValidadorDocumentoImp",
]
