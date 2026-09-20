from datetime import timedelta

import pytest

from domain.utils.fechas import ahora_utc
from infrastructure.persistencia.models import AccesoManual
from soporte.accesos import crear_acceso_manual


pytestmark = pytest.mark.integration


def _expirar_acceso(sesion_bd, formulario_id: str) -> None:
    acceso = (
        sesion_bd.query(AccesoManual)
        .filter_by(formulario_id=formulario_id)
        .one()
    )
    acceso.expires_at = ahora_utc() - timedelta(days=1)
    sesion_bd.commit()


def _credenciales_por_token(token: str) -> dict:
    return {"credenciales": {"token_diligenciamiento": token}}


def _credenciales_por_codigo_pin(codigo_peticion: str, pin: str) -> dict:
    return {
        "codigo_peticion": codigo_peticion,
        "pin": pin,
    }


def test_token_inexistente_no_resuelve_formulario(cliente_api):
    respuesta = cliente_api.get("/api/accesos-manuales/token/token-inexistente")

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "El enlace de diligenciamiento no es válido."


def test_codigo_inexistente_no_recupera_sesion(cliente_api):
    respuesta = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json=_credenciales_por_codigo_pin("SAG-NO-EXISTE", "PIN12345"),
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Código de petición o PIN incorrecto."


def test_pin_incorrecto_no_recupera_sesion(cliente_api):
    acceso = crear_acceso_manual(cliente_api)

    respuesta = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json=_credenciales_por_codigo_pin(acceso["codigo_peticion"], "PIN-MALO"),
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Código de petición o PIN incorrecto."


def test_token_incorrecto_no_autoriza_envio(cliente_api):
    acceso = crear_acceso_manual(cliente_api)

    respuesta = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json=_credenciales_por_token("token-equivocado"),
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Código de petición o PIN incorrecto."


def test_acceso_expirado_bloquea_link_y_recuperacion(
    cliente_api,
    sesion_bd,
):
    acceso = crear_acceso_manual(cliente_api)
    _expirar_acceso(sesion_bd, acceso["formulario_id"])

    respuesta_link = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )
    respuesta_recuperacion = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json=_credenciales_por_codigo_pin(acceso["codigo_peticion"], acceso["pin"]),
    )

    assert respuesta_link.status_code == 410
    assert respuesta_link.json()["detail"] == (
        "El acceso ha expirado. Solicite un nuevo enlace al área responsable."
    )
    assert respuesta_recuperacion.status_code == 410
    assert respuesta_recuperacion.json()["detail"] == (
        "El acceso ha expirado. Solicite un nuevo enlace al área responsable."
    )
