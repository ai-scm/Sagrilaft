"""
Tipos y helpers compartidos por los schemas HTTP.

Nota: por compatibilidad, algunos validadores aún dependen de helpers en
`services/`. En una siguiente iteración podemos moverlos a una capa shared/core.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional, TypeVar, Literal

from pydantic import BeforeValidator

from services.formulario.validacion_envio import _vacio_a_nulo
from services.utils.coercion import (
    coercionar_monto,
    coercionar_porcentaje,
    coercionar_porcentaje_participacion,
)
from core.fechas import a_iso_utc_z

T = TypeVar("T")


EnumLimpio = Annotated[Optional[T], BeforeValidator(_vacio_a_nulo)]

# Literales para estandarización estricta de Dropdowns fijos (sin enums complejos)
DropdownSiNo = Annotated[Literal["si", "no"] | None, BeforeValidator(_vacio_a_nulo)]
DropdownTipoId = Annotated[Literal["NIT", "CC", "CE", "PAS"] | None, BeforeValidator(_vacio_a_nulo)]

# Tipos reutilizables en cualquier schema que maneje montos o porcentajes
MontoPositivo = Annotated[Optional[float], BeforeValidator(coercionar_monto)]
PorcentajeValido = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje)]
PorcentajeParticipacion = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje_participacion)]


def a_iso_utc(valor: Optional[datetime]) -> Optional[str]:
    """Serializa un datetime a ISO-8601 con zona UTC explícita ('Z')."""
    return a_iso_utc_z(valor)
