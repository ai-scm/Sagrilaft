"""
Módulo core — configuración y contratos de la aplicación.

Re-exporta todos los símbolos públicos de configuracion.py y contratos.py
para que los importadores puedan usar tanto `from core import X`
como `from core.contratos import X`.
"""

from core.configuracion import AppConfig, AWSConfig, load_config
from core.contratos import (
    AlertaInconsistencia,
    HallazgoValidacion,
    IExtractorIA,
    IValidadorCruzado,
    IValidadorDocumento,
    ResultadoComparacion,
    ResultadoExtraccion,
)

__all__ = [
    # configuracion
    "AppConfig",
    "AWSConfig",
    "load_config",
    # contratos
    "AlertaInconsistencia",
    "HallazgoValidacion",
    "IExtractorIA",
    "IValidadorCruzado",
    "IValidadorDocumento",
    "ResultadoComparacion",
    "ResultadoExtraccion",
]
