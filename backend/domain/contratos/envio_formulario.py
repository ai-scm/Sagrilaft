"""
DTOs del intento de envío final del formulario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ErrorCampoFormulario:
    """Error de validación de un campo del formulario antes del envío."""
    campo: str
    mensaje: str


@dataclass
class ResultadoEnvioFormulario:
    """Resultado del intento de envío final de un formulario."""
    valido: bool
    errores: List["ErrorCampoFormulario"] = field(default_factory=list)
