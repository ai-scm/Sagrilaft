from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ValidacionResponse(BaseModel):
    id: str
    tipo: str
    campo: Optional[str] = None
    resultado: str
    detalle: Optional[str] = None
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

