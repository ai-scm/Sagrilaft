"""
Contrato (Protocol) para proveedores de listas de cautela.

OCP : agregar nuevas listas (SARLAFT, GAFILAT, etc.) solo requiere
      implementar IProveedorListaCautela — sin modificar el servicio.
DIP : ListaCautelaService depende de esta abstracción, no de implementaciones concretas.
"""

from typing import Optional, Protocol, runtime_checkable

from schemas import ResultadoListaCautela


@runtime_checkable
class IProveedorListaCautela(Protocol):
    """
    Interfaz para proveedores de listas de cautela.

    Para integrar una lista real (ej. API OFAC), crear una clase que implemente
    este protocolo sin necesidad de modificar ListaCautelaService.
    """

    nombre: str
    """Nombre identificador de la lista (ej. 'OFAC (EE.UU.)')."""

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        """
        Busca un nombre e identificación en esta lista.

        Args:
            nombre:    Nombre completo a buscar (normalización interna del proveedor).
            numero_id: Número de identificación (opcional, si el proveedor lo soporta).

        Returns:
            ResultadoListaCautela con estado de coincidencia, detalle y nivel de riesgo.
        """
        ...
