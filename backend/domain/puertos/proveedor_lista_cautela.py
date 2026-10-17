"""
Puerto para proveedores individuales de listas de cautela.

Distinto de `consultor_listas_cautela.ConsultorListasCautela`: aquel modela
un único proveedor externo consolidado de verificación SAGRILAFT (con
descarga de PDF), mientras que este modela N proveedores de listas
individuales (OFAC, ONU, Procuraduría, etc.) que `ListaCautelaService`
consulta y agrega.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from domain.contratos.listas import ResultadoBusquedaLista


@runtime_checkable
class ProveedorListaCautelaImp(Protocol):
    """
    Puerto para proveedores de listas de cautela (OFAC, ONU, Procuraduría, etc.).

    OCP: agregar una lista nueva solo requiere implementar este Protocol.
    DIP: ListaCautelaService depende de esta abstracción, no de implementaciones.
    """

    nombre: str

    def buscar(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> ResultadoBusquedaLista:
        """Busca un nombre e identificación en esta lista de cautela."""
        ...
