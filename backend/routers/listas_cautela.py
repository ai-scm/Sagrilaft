from fastapi import APIRouter, Request
from schemas import BusquedaListaCautela, RespuestaListaCautela
from services.lista_cautela_service import ListaCautelaService

router = APIRouter(prefix="/api/listas-cautela", tags=["listas de cautela"])


def _get_servicio(request: Request) -> ListaCautelaService:
    return request.app.state.lista_cautela_service


@router.post("/buscar", response_model=RespuestaListaCautela)
def buscar_en_listas(busqueda: BusquedaListaCautela, request: Request):
    """
    Busca un nombre y/o número de identificación en listas de cautela públicas:
    - OFAC (EE.UU.)
    - Naciones Unidas
    - Procuraduría General de la Nación
    - Contraloría General de la República
    - Policía Nacional
    """
    servicio = _get_servicio(request)
    resultados = servicio.buscar_todas_listas(busqueda.nombre, busqueda.numero_identificacion)
    riesgo = ListaCautelaService.calcular_riesgo_general(resultados)
    return RespuestaListaCautela(
        nombre_buscado=busqueda.nombre,
        resultados=resultados,
        riesgo_general=riesgo,
    )
