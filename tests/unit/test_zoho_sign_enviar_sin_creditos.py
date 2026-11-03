"""
crear_solicitud_firma_multiple no distinguia "ZohoSign sin creditos para
enviar por API" (HTTP 400, code 12000) de cualquier otro error generico: el
submit fallaba con RuntimeError y el endpoint /enviar-a-firma respondia 500
sin pista alguna. Confirmado en produccion 2026-11-03 al intentar enviar un
expediente real: la cuenta oficial de ZohoSign no tenia plan/creditos de API.
"""
from unittest.mock import patch

import httpx
import pytest

from domain.excepciones import ZohoSignSinCreditosError
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
_RESPUESTA_CREAR_OK = _respuesta(
    200,
    b'{"code":0,"requests":{"request_id":"req-1",'
    b'"actions":[{"action_id":"act-1"}],"document_ids":["doc-1"]}}',
)
_RESPUESTA_SUBMIT_SIN_CREDITOS = _respuesta(
    400,
    b'{"code":12000,"message":"Compre creditos de Zoho Sign para enviar '
    b'documentos a traves de la API.","status":"failure"}',
)


def test_submit_sin_creditos_levanta_zoho_sign_sin_creditos(tmp_path):
    pdf = tmp_path / "formulario.pdf"
    pdf.write_bytes(b"%PDF-1.4 contenido de prueba")
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_RESPUESTA_TOKEN_OK, _RESPUESTA_CREAR_OK, _RESPUESTA_SUBMIT_SIN_CREDITOS],
    ):
        with pytest.raises(ZohoSignSinCreditosError):
            servicio.crear_solicitud_firma_multiple(
                [pdf], "Expediente de prueba", "firmante@ejemplo.com", "Firmante de Prueba",
            )


def test_submit_400_sin_code_12000_no_se_confunde_con_sin_creditos(tmp_path):
    pdf = tmp_path / "formulario.pdf"
    pdf.write_bytes(b"%PDF-1.4 contenido de prueba")
    servicio = ZohoSignService(_config_rapida())
    respuesta_otro_error_400 = _respuesta(400, b'{"code":9999,"message":"otro problema"}')

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_RESPUESTA_TOKEN_OK, _RESPUESTA_CREAR_OK, respuesta_otro_error_400],
    ):
        with pytest.raises(RuntimeError) as excinfo:
            servicio.crear_solicitud_firma_multiple(
                [pdf], "Expediente de prueba", "firmante@ejemplo.com", "Firmante de Prueba",
            )
        assert not isinstance(excinfo.value, ZohoSignSinCreditosError)
