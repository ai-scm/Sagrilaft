"""
Contrato (Protocol) para proveedores de listas de cautela.

OCP: agregar nuevas listas (SARLAFT, GAFILAT, etc.) solo requiere
     implementar IListaCautelaProvider — sin modificar el servicio.
DIP: ListaCautelaService depende de esta abstracción, no de implementaciones concretas.
"""
from typing import Optional, Protocol, runtime_checkable
from schemas import ResultadoListaCautela


@runtime_checkable
class IListaCautelaProvider(Protocol):
    """
    Interfaz para proveedores de listas de cautela.

    Para integrar una lista real (ej. OFAC API), crear una clase que implemente
    este protocolo sin modificar ListaCautelaService.
    """
    nombre: str

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        """
        Busca un nombre/identificación en esta lista.

        Args:
            nombre: Nombre completo a buscar (normalización interna del provider).
            numero_id: Número de identificación (opcional, usado si el provider lo soporta).

        Returns:
            ResultadoListaCautela con found status, detail, and risk level.
        """
        ...
