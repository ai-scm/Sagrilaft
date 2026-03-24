"""
Servicio de búsqueda en listas de cautela públicas.
Mock para prototipo - en producción se conectaría con APIs reales.
"""

from typing import List, Optional
from schemas import ResultadoListaCautela


# Datos mock de ejemplo para listas de cautela
MOCK_LISTA_OFAC = [
    "juan pablo escobar",
    "carlos lehder",
    "gonzalo rodriguez gacha",
]

MOCK_LISTA_ONU = [
    "osama bin laden",
    "ayman al zawahiri",
]

MOCK_LISTA_PROCURADURIA = [
    "funcionario ejemplo sancionado",
]


class ListaCautelaService:
    """
    Servicio para verificar nombres contra listas de cautela públicas.
    En producción:
    - OFAC: https://sanctionssearch.ofac.treas.gov/
    - ONU: https://www.un.org/securitycouncil/content/un-sc-consolidated-list
    - Procuraduría General: https://www.procuraduria.gov.co/
    - Contraloría General: https://www.contraloria.gov.co/
    - Policía Nacional (antecedentes)
    """

    @staticmethod
    def normalizar_nombre(nombre: str) -> str:
        """Normaliza nombre para comparación."""
        return nombre.lower().strip()

    @staticmethod
    def buscar_en_lista(nombre: str, lista: List[str], nombre_lista: str) -> ResultadoListaCautela:
        """Busca un nombre en una lista específica."""
        nombre_norm = ListaCautelaService.normalizar_nombre(nombre)

        # Búsqueda parcial (si algún token del nombre está en la lista)
        encontrado = False
        detalle = None

        for entrada in lista:
            if nombre_norm in entrada or entrada in nombre_norm:
                encontrado = True
                detalle = f"Coincidencia encontrada en {nombre_lista}: '{entrada}'"
                break

        return ResultadoListaCautela(
            lista=nombre_lista,
            encontrado=encontrado,
            detalle=detalle if encontrado else f"Sin coincidencias en {nombre_lista}",
            nivel_riesgo="alto" if encontrado else "bajo"
        )

    @staticmethod
    def buscar_todas_listas(
        nombre: str,
        numero_identificacion: Optional[str] = None
    ) -> List[ResultadoListaCautela]:
        """
        Busca un nombre/identificación en todas las listas de cautela configuradas.
        """
        resultados = []

        # OFAC
        resultados.append(
            ListaCautelaService.buscar_en_lista(nombre, MOCK_LISTA_OFAC, "OFAC (EE.UU.)")
        )

        # ONU
        resultados.append(
            ListaCautelaService.buscar_en_lista(nombre, MOCK_LISTA_ONU, "Naciones Unidas")
        )

        # Procuraduría
        resultados.append(
            ListaCautelaService.buscar_en_lista(
                nombre, MOCK_LISTA_PROCURADURIA, "Procuraduría General de la Nación"
            )
        )

        # Contraloría (mock vacío)
        resultados.append(ResultadoListaCautela(
            lista="Contraloría General de la República",
            encontrado=False,
            detalle="Sin coincidencias en Contraloría",
            nivel_riesgo="bajo"
        ))

        # Policía Nacional (mock vacío)
        resultados.append(ResultadoListaCautela(
            lista="Policía Nacional (Antecedentes)",
            encontrado=False,
            detalle="Sin coincidencias en base de antecedentes",
            nivel_riesgo="bajo"
        ))

        return resultados

    @staticmethod
    def calcular_riesgo_general(resultados: List[ResultadoListaCautela]) -> str:
        """Calcula el nivel de riesgo general basado en los resultados."""
        encontrados = [r for r in resultados if r.encontrado]

        if len(encontrados) >= 2:
            return "alto"
        elif len(encontrados) == 1:
            return "medio"
        return "bajo"
