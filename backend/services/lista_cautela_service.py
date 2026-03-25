"""
Servicio de búsqueda en listas de cautela.

Recibe una lista de providers via inyección de dependencias.
Para integrar una lista real, agregar un nuevo IProveedorListaCautela en
services/listas/mock_providers.py (o crear un módulo real_providers.py)
y registrarlo en main.py — sin tocar esta clase.
"""
from typing import Optional
from schemas import ResultadoListaCautela
from services.listas.contracts import IProveedorListaCautela


class ListaCautelaService:
    def __init__(self, providers: list[IProveedorListaCautela]):
        self._providers = providers

    def buscar_todas_listas(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> list[ResultadoListaCautela]:
        """Busca en todos los providers registrados."""
        return [p.buscar(nombre, numero_identificacion) for p in self._providers]

    @staticmethod
    def calcular_riesgo_general(resultados: list[ResultadoListaCautela]) -> str:
        """Calcula nivel de riesgo consolidado (alto/medio/bajo)."""
        encontrados = sum(1 for r in resultados if r.encontrado)
        if encontrados >= 2:
            return "alto"
        if encontrados == 1:
            return "medio"
        return "bajo"
