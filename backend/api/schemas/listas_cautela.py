from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BusquedaListaCautela(BaseModel):
    nombre: str
    numero_identificacion: Optional[str] = None


class ResultadoListaCautela(BaseModel):
    lista: str
    encontrado: bool
    detalle: Optional[str] = None
    nivel_riesgo: Optional[str] = None  # "bajo", "medio", "alto"


class RespuestaListaCautela(BaseModel):
    nombre_buscado: str
    resultados: List[ResultadoListaCautela] = Field(default_factory=list)
    riesgo_general: str = "bajo"  # "bajo", "medio", "alto"

