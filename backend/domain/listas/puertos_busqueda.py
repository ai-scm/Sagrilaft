"""Puerto previsto de F6; los adaptadores no seleccionan fuentes activas ni deciden riesgo."""
from typing import Protocol

from .contratos_busqueda import CapacidadesBusqueda, ResultadoBusquedaF6, SolicitudBusquedaInterna


class ConsultorBusqueda(Protocol):
    def capacidades(self) -> CapacidadesBusqueda: ...
    def consultar(self, solicitud: SolicitudBusquedaInterna) -> ResultadoBusquedaF6: ...
