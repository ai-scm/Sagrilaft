"""
Migracion de python-jose a PyJWT (api/middleware/autenticacion.py).

python-jose quedo sin mantenimiento (ultimo release: 2021) y acumulaba 4 CVEs
sin parche posible. Estas pruebas fabrican un par de claves RSA y un JWKS con
el mismo formato que publica Keycloak (RSAAlgorithm.to_jwk) para verificar
que _decodificar_jwt con PyJWT:

  - acepta un token valido firmado con la clave correcta y selecciona la
    clave por "kid" dentro del JWKS (igual que hacia python-jose internamente)
  - rechaza una firma invalida, un token expirado, un "kid" desconocido,
    un "azp" que no coincide con el client_id configurado y un payload sin "sub"
  - no rompe el fallback a cache stale de JWKS cuando Keycloak no responde

No sustituye una prueba de integracion contra un Keycloak real corriendo en
docker-compose.dev (ver PENDIENTES_PRODUCCION.md), pero cubre la logica de
decodificacion que antes dependia de python-jose.
"""
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from api.middleware.autenticacion import _decodificar_jwt, _obtener_jwks
import api.middleware.autenticacion as autenticacion_mod
from infrastructure.config.configuracion import KeycloakConfig


@pytest.fixture
def anyio_backend():
    """Las dependencies de FastAPI corren sobre asyncio; no se requiere trio."""
    return "asyncio"

_ISSUER = "https://keycloak.test/realms/sagrilaft"
_CLIENT_ID = "sagrilaft-portal"
_KID = "clave-test-1"


def _par_de_claves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return privada, privada.public_key()


_PRIVADA, _PUBLICA = _par_de_claves()
_OTRA_PRIVADA, _ = _par_de_claves()


def _jwks_dict() -> dict:
    jwk = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(_PUBLICA, as_dict=True)
    jwk["kid"] = _KID
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def _token(
    *,
    clave_privada=None,
    kid=_KID,
    sub="abc-123",
    azp=_CLIENT_ID,
    exp_delta=3600,
    issuer=_ISSUER,
    audience=_CLIENT_ID,
    roles=("acceso_clientes",),
    sin_sub=False,
) -> str:
    clave_privada = clave_privada or _PRIVADA
    ahora = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "azp": azp,
        "iat": ahora,
        "exp": ahora + exp_delta,
        "email": "operador@sagrilaft.test",
        "realm_access": {"roles": list(roles)},
    }
    if not sin_sub:
        payload["sub"] = sub
    headers = {"kid": kid} if kid else {}
    return jwt.encode(payload, clave_privada, algorithm="RS256", headers=headers)


class _RequestFalso:
    """Doble minimo de fastapi.Request para las partes que usa _decodificar_jwt."""

    def __init__(self):
        self.client = type("Cliente", (), {"host": "10.0.0.5"})()
        self.headers = {"user-agent": "pytest"}
        self.url = type("Url", (), {"path": "/api/expedientes"})()


def _config_keycloak() -> KeycloakConfig:
    return KeycloakConfig(
        url="https://keycloak.test",
        realm="sagrilaft",
        client_id=_CLIENT_ID,
        issuer_url="https://keycloak.test",
    )


@pytest.fixture(autouse=True)
def _jwks_cacheado(monkeypatch):
    """Evita llamadas HTTP reales: precarga el cache interno del modulo."""
    monkeypatch.setattr(autenticacion_mod, "_jwks_cache", _jwks_dict())
    monkeypatch.setattr(autenticacion_mod, "_jwks_cache_ts", time.monotonic())
    yield
    monkeypatch.setattr(autenticacion_mod, "_jwks_cache", None)
    monkeypatch.setattr(autenticacion_mod, "_jwks_cache_ts", 0.0)


@pytest.mark.anyio
async def test_token_valido_selecciona_clave_por_kid_y_decodifica():
    token = _token()
    usuario = await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert usuario.sub == "abc-123"
    assert usuario.email == "operador@sagrilaft.test"
    assert usuario.tiene_rol("acceso_clientes")


@pytest.mark.anyio
async def test_firma_invalida_se_rechaza():
    token = _token(clave_privada=_OTRA_PRIVADA)  # firmado con una clave que no esta en el JWKS

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_token_expirado_se_rechaza():
    token = _token(exp_delta=-10)

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_kid_desconocido_se_rechaza():
    token = _token(kid="kid-que-no-existe-en-el-jwks")

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_azp_distinto_al_cliente_configurado_se_rechaza():
    token = _token(azp="otro-cliente-keycloak")

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401
    assert "cliente distinto" in exc_info.value.detail


@pytest.mark.anyio
async def test_token_sin_sub_se_rechaza():
    token = _token(sin_sub=True)

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401
    assert "identificador de usuario ausente" in exc_info.value.detail


@pytest.mark.anyio
async def test_issuer_distinto_se_rechaza():
    token = _token(issuer="https://otro-keycloak.test/realms/otro")

    with pytest.raises(Exception) as exc_info:
        await _decodificar_jwt(token, _config_keycloak(), _RequestFalso())

    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_obtener_jwks_usa_cache_stale_si_keycloak_no_responde(monkeypatch):
    """La migracion no debe romper el fallback a cache stale (A10:2025)."""
    autenticacion_mod._jwks_cache = {"keys": [{"kid": "viejo"}]}
    autenticacion_mod._jwks_cache_ts = time.monotonic() - 10_000  # cache vencido

    class _ClienteQueFalla:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("Keycloak no disponible")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _ClienteQueFalla())

    resultado = await _obtener_jwks(_config_keycloak())

    assert resultado == {"keys": [{"kid": "viejo"}]}
