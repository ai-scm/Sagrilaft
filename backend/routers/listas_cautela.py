"""
Router de listas de cautela.

Expone el endpoint de búsqueda en listas públicas de control de riesgo:
OFAC, Naciones Unidas, Procuraduría, Contraloría y Policía Nacional.

SRP : responsabilidad única de recibir la solicitud HTTP y retornar la respuesta.
      La orquestación de búsqueda + cálculo de riesgo + construcción de respuesta
      vive en ListaCautelaService.buscar_y_evaluar — no en este router.
DIP : delega completamente en ListaCautelaService mediante inyección de dependencias.
"""

from fastapi import APIRouter, Depends

from dependencies import obtener_servicio_lista_cautela
from schemas import BusquedaListaCautela, RespuestaListaCautela
from services.lista_cautela_service import ListaCautelaService

enrutador = APIRouter(prefix="/api/listas-cautela", tags=["listas de cautela"])


# ─── Endpoints ───────────────────────────────────────────────────────────────

@enrutador.post("/buscar", response_model=RespuestaListaCautela)
def buscar_en_listas(
    busqueda: BusquedaListaCautela,
    servicio: ListaCautelaService = Depends(obtener_servicio_lista_cautela),
) -> RespuestaListaCautela:
    """
    Busca un nombre y/o número de identificación en las listas de cautela:
    - OFAC (EE.UU.)
    - Naciones Unidas
    - Procuraduría General de la Nación
    - Contraloría General de la República
    - Policía Nacional
    """
    return servicio.buscar_y_evaluar(
        busqueda.nombre,
        busqueda.numero_identificacion,
    )
