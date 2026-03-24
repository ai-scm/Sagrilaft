from fastapi import APIRouter
from schemas import BusquedaListaCautela, RespuestaListaCautela
from services.lista_cautela_service import ListaCautelaService

router = APIRouter(prefix="/api/listas-cautela", tags=["listas de cautela"])


@router.post("/buscar", response_model=RespuestaListaCautela)
def buscar_en_listas(busqueda: BusquedaListaCautela):
    """
    Busca un nombre y/o número de identificación en listas de cautela públicas:
    - OFAC (EE.UU.)
    - Naciones Unidas
    - Procuraduría General de la Nación
    - Contraloría General de la República
    - Policía Nacional
    """
    resultados = ListaCautelaService.buscar_todas_listas(
        busqueda.nombre,
        busqueda.numero_identificacion
    )

    riesgo = ListaCautelaService.calcular_riesgo_general(resultados)

    return RespuestaListaCautela(
        nombre_buscado=busqueda.nombre,
        resultados=resultados,
        riesgo_general=riesgo
    )
