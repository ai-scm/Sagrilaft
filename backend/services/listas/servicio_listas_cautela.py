"""
Servicio de búsqueda en listas de cautela SAGRILAFT.

Organiza responsabilidades en dos clases cohesivas:
  - CalculadorNivelRiesgo: calcula el nivel de riesgo consolidado (SRP, OCP).
  - ListaCautelaService:   coordina búsqueda y evaluación de riesgo (SRP, DIP).

SOLID:
- S (Responsabilidad Única): búsqueda y cálculo de riesgo en clases separadas.
- O (Abierto/Cerrado): umbrales de riesgo configurables; nuevas listas se agregan
  registrando un IProveedorListaCautela en main.py sin tocar estas clases.
- D (Inversión de Dependencias): ListaCautelaService recibe CalculadorNivelRiesgo
  por constructor; ambos dependen de abstracciones, no de implementaciones.

Código reubicado: la construcción de RespuestaListaCautela y el cálculo de
riesgo vivían en el router — ahora están correctamente en este servicio.
"""

from typing import List, Optional

from schemas import ResultadoListaCautela, RespuestaListaCautela
from services.listas.protocolo_listas import IProveedorListaCautela


# ═══════════════════════════════════════════════════════════════
# Calculador de nivel de riesgo
# ═══════════════════════════════════════════════════════════════

class CalculadorNivelRiesgo:
    """
    Calcula el nivel de riesgo consolidado a partir de los resultados de búsqueda.

    SOLID - S: Responsabilidad única — determinar el nivel de riesgo.
    SOLID - O: Los umbrales son configurables en el constructor; cambiar los
               criterios no requiere modificar ListaCautelaService.

    Niveles posibles: "bajo", "medio", "alto".
    """

    def __init__(
        self,
        umbral_alto: int = 2,
        umbral_medio: int = 1,
    ) -> None:
        """
        Args:
            umbral_alto:  Cantidad mínima de coincidencias para nivel "alto".
            umbral_medio: Cantidad mínima de coincidencias para nivel "medio".
        """
        self._umbral_alto = umbral_alto
        self._umbral_medio = umbral_medio

    def calcular(self, resultados: List[ResultadoListaCautela]) -> str:
        """
        Determina el nivel de riesgo según cuántas listas reportaron coincidencia.

        Args:
            resultados: Resultados de búsqueda en todas las listas consultadas.

        Returns:
            "alto", "medio" o "bajo" según los umbrales configurados.
        """
        total_coincidencias = sum(1 for resultado in resultados if resultado.encontrado)

        if total_coincidencias >= self._umbral_alto:
            return "alto"
        if total_coincidencias >= self._umbral_medio:
            return "medio"
        return "bajo"


# ═══════════════════════════════════════════════════════════════
# Servicio principal
# ═══════════════════════════════════════════════════════════════

class ListaCautelaService:
    """
    Coordina la búsqueda en listas de cautela y la evaluación de riesgo.

    Para integrar una lista real, registrar un nuevo IProveedorListaCautela
    en main.py — sin modificar esta clase (OCP).

    SOLID - D: Recibe IProveedorListaCautela y CalculadorNivelRiesgo por
               constructor; no depende de implementaciones concretas.
    """

    def __init__(
        self,
        proveedores: List[IProveedorListaCautela],
        calculador_riesgo: Optional[CalculadorNivelRiesgo] = None,
    ) -> None:
        """
        Args:
            proveedores:       Lista de proveedores de listas de cautela.
            calculador_riesgo: Calculador de nivel de riesgo. Si no se provee,
                               usa los umbrales predeterminados (≥2 alto, ≥1 medio).
        """
        self._proveedores = proveedores
        self._calculador_riesgo = calculador_riesgo or CalculadorNivelRiesgo()

    # ─── Métodos públicos ─────────────────────────────────────────────────────

    def buscar_todas_listas(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> List[ResultadoListaCautela]:
        """
        Consulta todos los proveedores registrados y retorna sus resultados.

        Args:
            nombre:               Nombre completo a buscar.
            numero_identificacion: Número de identificación (opcional).

        Returns:
            Un ResultadoListaCautela por cada proveedor registrado.
        """
        return [
            proveedor.buscar(nombre, numero_identificacion)
            for proveedor in self._proveedores
        ]

    def buscar_y_evaluar(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> RespuestaListaCautela:
        """
        Busca en todas las listas y calcula el nivel de riesgo consolidado.

        Encapsula el flujo completo: búsqueda + evaluación + construcción de
        respuesta. El router delega aquí en lugar de orquestar estos pasos.

        Args:
            nombre:               Nombre completo a buscar.
            numero_identificacion: Número de identificación (opcional).

        Returns:
            RespuestaListaCautela con resultados individuales y riesgo general.
        """
        resultados = self.buscar_todas_listas(nombre, numero_identificacion)
        nivel_riesgo = self._calculador_riesgo.calcular(resultados)
        return RespuestaListaCautela(
            nombre_buscado=nombre,
            resultados=resultados,
            riesgo_general=nivel_riesgo,
        )
