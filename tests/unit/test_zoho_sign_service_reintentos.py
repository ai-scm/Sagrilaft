"""
CA1/CA2 — traduccion de fallos de ZohoSign a excepciones de dominio.

Ver docs/RUNBOOK_OPERATIVO.md seccion 2 y la spec aprobada: un error
transitorio (429/502/503/504 o de red) que agota los reintentos debe
levantar ZohoSignIndisponibleError; un error de autenticacion (401/403)
debe levantar ZohoSignAutenticacionError. La politica de reintentos
(intentos, backoff, codigos reintentables) no cambia.
"""
from unittest.mock import patch

import httpx
import pytest

from domain.excepciones import ZohoSignAutenticacionError, ZohoSignIndisponibleError
from infrastructure.config.configuracion import ZohoSignConfig
from infrastructure.zoho_sign.zoho_sign_service import ZohoSignService

_URL_PRUEBA = "https://sign.zoho.com/api/v1/requests/fake"
_URL_TOKEN = "https://accounts.zoho.com/oauth/v2/token"


def _config_rapida(**overrides) -> ZohoSignConfig:
    """Config con reintentos rapidos (mismos 3 intentos/backoff salvo overrides)."""
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


def test_ca1_error_transitorio_agotado_levanta_zoho_sign_indisponible():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        return_value=_respuesta(503),
    ) as mock_request:
        with pytest.raises(ZohoSignIndisponibleError):
            servicio._ejecutar_peticion_con_reintentos("GET", _URL_PRUEBA, timeout=1)

    assert mock_request.call_count == 3, "debe agotar exactamente los 3 intentos configurados"


def test_ca1_falla_de_red_agotada_levanta_zoho_sign_indisponible():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=httpx.ConnectError("boom"),
    ) as mock_request:
        with pytest.raises(ZohoSignIndisponibleError):
            servicio._ejecutar_peticion_con_reintentos("GET", _URL_PRUEBA, timeout=1)

    assert mock_request.call_count == 3


def test_error_transitorio_que_se_resuelve_no_se_ve_afectado():
    """La politica de reintentos sigue intacta: si el 2do intento tiene exito, no se levanta nada."""
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        side_effect=[_respuesta(503), _respuesta(200)],
    ) as mock_request:
        resp = servicio._ejecutar_peticion_con_reintentos("GET", _URL_PRUEBA, timeout=1)

    assert resp.status_code == 200
    assert mock_request.call_count == 2


def test_ca2_401_al_refrescar_token_levanta_zoho_sign_autenticacion():
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        return_value=_respuesta(401),
    ):
        with pytest.raises(ZohoSignAutenticacionError):
            servicio._obtener_token()


def test_error_no_reintentable_distinto_de_auth_no_se_traduce():
    """
    Un 400 (no reintentable, no es 401/403) no debe traducirse a ninguna de
    las 2 excepciones nuevas -- comportamiento fuera del alcance de CA1/CA2,
    debe permanecer como httpx.HTTPStatusError sin envolver.
    """
    servicio = ZohoSignService(_config_rapida())

    with patch(
        "infrastructure.zoho_sign.zoho_sign_service.httpx.request",
        return_value=_respuesta(400),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            servicio._obtener_token()
