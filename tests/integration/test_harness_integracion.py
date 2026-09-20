import pytest


pytestmark = pytest.mark.integration


def test_harness_expone_api_real_con_dependencias_controladas(
    cliente_api,
    dependencias_dobles,
):
    respuesta = cliente_api.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "healthy"
    assert dependencias_dobles["storage"].existe("archivo-de-prueba.txt") is False
    assert dependencias_dobles["alertas_portal"].metricas() == {
        "enviadas": 0,
        "fallidas": 0,
    }
