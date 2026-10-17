"""
DTOs de resultados de búsqueda en listas de cautela.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResultadoBusquedaLista:
    """Resultado de consultar un proveedor de listas de cautela."""
    lista: str
    encontrado: bool
    detalle: Optional[str] = None
    nivel_riesgo: Optional[str] = None  # "bajo" | "medio" | "alto"


@dataclass
class RespuestaBusquedaLista:
    """Respuesta consolidada de búsqueda en todas las listas de cautela."""
    nombre_buscado: str
    resultados: List[ResultadoBusquedaLista] = field(default_factory=list)
    riesgo_general: str = "bajo"  # "bajo" | "medio" | "alto"
