import pytest

from soporte.accesos import crear_acceso_manual


pytestmark = pytest.mark.integration


def test_rate_limit_bloquea_recuperacion_por_codigo_pin_tras_intentos_invalidos(
    cliente_api,
):
    acceso = crear_acceso_manual(cliente_api)

    for _ in range(5):
        respuesta = cliente_api.post(
            "/api/formularios/sesion/recuperar-por-acceso",
            json={
                "codigo_peticion": acceso["codigo_peticion"],
                "pin": "000000",
            },
        )
        assert respuesta.status_code == 401, respuesta.text

    respuesta_limitada = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json={
            "codigo_peticion": acceso["codigo_peticion"],
            "pin": "000000",
        },
    )

    assert respuesta_limitada.status_code == 429, respuesta_limitada.text
    assert respuesta_limitada.json() == {
        "detail": "Demasiadas solicitudes. Intente más tarde."
    }


def test_rate_limit_bloquea_envio_final_con_token_incorrecto_tras_intentos_invalidos(
    cliente_api,
):
    acceso = crear_acceso_manual(cliente_api)

    for _ in range(10):
        respuesta = cliente_api.post(
            f"/api/formularios/{acceso['formulario_id']}/enviar",
            json={
                "credenciales": {
                    "token_diligenciamiento": "token-invalido",
                },
            },
        )
        assert respuesta.status_code == 401, respuesta.text

    respuesta_limitada = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": "token-invalido",
            },
        },
    )

    assert respuesta_limitada.status_code == 429, respuesta_limitada.text
    assert respuesta_limitada.json() == {
        "detail": "Demasiadas solicitudes. Intente más tarde."
    }
