from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer

from .comunes import a_iso_utc


class ValidacionResponse(BaseModel):
    id: str
    tipo: str
    campo: Optional[str] = None
    resultado: str
    detalle: Optional[str] = None
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""

    class Config:
        from_attributes = True

