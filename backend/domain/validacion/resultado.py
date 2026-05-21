from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ResultadoValidacionDominio:
    """
    Value Object que representa un resultado de validación ya persistido.

    Desacopla la capa de servicios del ORM: ValidacionService retorna esta
    clase en vez de ResultadoValidacion (SQLAlchemy). El router usa from_attributes
    para mapearlo a ValidacionResponse sin cambios de contrato HTTP.
    """

    id: str
    formulario_id: str
    tipo: str
    campo: Optional[str]
    resultado: str
    detalle: Optional[str]
    valor_formulario: Optional[str]
    valor_documento: Optional[str]
    created_at: datetime
