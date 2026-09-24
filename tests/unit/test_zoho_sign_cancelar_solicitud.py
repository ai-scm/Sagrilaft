"""
cancelar_solicitud_firma no traducia errores HTTP a excepciones de dominio
(a diferencia de crear_solicitud_firma_multiple/_obtener_token, que ya lo
hacian). Un 400 real de ZohoSign (recall rechazado porque la solicitud ya
esta firmada/expirada/cancelada) se propagaba como httpx.HTTPStatusError
sin envolver, y el endpoint /cancelar-firma respondia 500 en vez de un
error claro. Confirmado en staging 2026-09-24 al intentar cancelar un
expediente ya completado.
"""
from unittest.mock import patch

import httpx
import pytest

from domain.excepciones import (
    ZohoSignAutenticacionError,
    ZohoSignSolicitudNoCancelableError,
)
from infrastructure.config.configuracion import ZohoSignConfig
from infrastructure.zoho_sign.zoho_sign_service import ZohoSignService

_URL_PRUEBA = "https://sign.zoho.com/api/v1/requests/fake"


def _config_rapida(**overrides) -> ZohoSignConfig:
    base = {
        "max_intentos_http": 3,
        "espera_inicial_reintento_segundos": 0.0,
        "factor_backoff_exponencial": 2,
    }
    base.update(overrides)
    return ZohoSignConfig(**base)


def _respuesta(status_code: int, contenido: bytes = b"{}") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=contenido,
        request=httpx.Request("GET", _URL_PRUEBA),
    )


_RESPUESTA_TOKEN_OK = _respuesta(200, b'{"access_token":"tok","expires_in":3600}')


def test_recall_400_levanta_solicitud_no_cancelable():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_RESPUESTA_TOKEN_OK, _respuesta(400, b'{"message":"already completed"}')],
    ):
        with pytest.raises(ZohoSignSolicitudNoCancelableError):
            servicio.cancelar_solicitud_firma("req-1")


def test_recall_401_levanta_autenticacion():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_RESPUESTA_TOKEN_OK, _respuesta(401)],
    ):
        with pytest.raises(ZohoSignAutenticacionError):
            servicio.cancelar_solicitud_firma("req-1")


def test_recall_exitoso_no_lanza_nada():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_RESPUESTA_TOKEN_OK, _respuesta(200, b'{"code":0}')],
    ):
        servicio.cancelar_solicitud_firma("req-1")
