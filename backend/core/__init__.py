"""
Módulo core — configuración y contratos de la aplicación.

Re-exporta todos los símbolos públicos de configuracion.py y contratos.py
para que los importadores puedan usar tanto `from core import X`
como `from core.contratos import X`.
"""

from core.configuracion import AWSConfig, AppConfig, load_config
from core.contratos import (
    ResultadoExtraccion,
    HallazgoValidacion,
    ResultadoComparacion,
    AlertaInconsistencia,
    ExtractorIAImp,
    ValidadorDocumentoImp,
    ValidadorCruzadoImp,
)

__all__ = [
    # configuracion
    "AWSConfig",
    "AppConfig",
    "load_config",
    # contratos
    "ResultadoExtraccion",
    "HallazgoValidacion",
    "ResultadoComparacion",
    "AlertaInconsistencia",
    "ExtractorIAImp",
    "ValidadorDocumentoImp",
    "ValidadorCruzadoImp",
]
