"""
Tipos y helpers compartidos por los schemas HTTP.

Nota: por compatibilidad, algunos validadores aún dependen de helpers en
`services/`. En una siguiente iteración podemos moverlos a una capa shared/core.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional, TypeVar, Literal

from pydantic import BeforeValidator, BaseModel

from domain.utils.coercion import (
    coercionar_bool_si_no,
    coercionar_fecha_colombia,
    coercionar_monto,
    coercionar_porcentaje,
    coercionar_porcentaje_participacion,
    vacio_a_nulo,
)
from domain.utils.fechas import a_iso_utc_z

T = TypeVar("T")


EnumLimpio = Annotated[Optional[T], BeforeValidator(vacio_a_nulo)]

# Literales para estandarización estricta de Dropdowns fijos (sin enums complejos)
DropdownSiNo = Annotated[Literal["si", "no"] | None, BeforeValidator(vacio_a_nulo)]
DropdownTipoId = Annotated[Literal["NIT", "CC", "CE", "PAS"] | None, BeforeValidator(vacio_a_nulo)]

# Tipos reutilizables en cualquier schema que maneje montos o porcentajes
BooleanoFormulario = Annotated[Optional[bool], BeforeValidator(coercionar_bool_si_no)]
FechaFormulario = Annotated[Optional[date], BeforeValidator(coercionar_fecha_colombia)]
MontoPositivo = Annotated[Optional[Decimal], BeforeValidator(coercionar_monto)]
PorcentajeValido = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje)]
PorcentajeParticipacion = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje_participacion)]


def a_iso_utc(valor: Optional[datetime]) -> Optional[str]:
    """Serializa un datetime a ISO-8601 con zona UTC explícita ('Z')."""
    return a_iso_utc_z(valor)


class FechaServidorResponse(BaseModel):
    """Fecha actual del servidor, normalizada a la zona horaria de Colombia."""

    dia: int
    mes: int
    year: int
    iso: str
