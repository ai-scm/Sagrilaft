"""
Middleware de autenticación — Keycloak.

Valida tokens JWT emitidos por Keycloak contra las claves públicas JWKS.
Las claves se cachean durante 1 hora para reducir llamadas al servidor de identidad.

Rutas protegidas por `portal_interno`:
  - Todos los endpoints de /api/expedientes/*
  - POST /api/accesos-manuales/         (crear acceso)
  - GET  /api/accesos-manuales/         (listar accesos)

Rutas públicas (sin esta dependency):
  - POST /api/formularios/*                       (acceso por token de tercero)
  - POST /api/webhooks/*                          (callbacks Zoho Sign — autenticados por HMAC)
  - GET  /api/accesos-manuales/token/{token}      (enlace externo al destinatario)
"""

import logging
import os
import time

import httpx
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from infrastructure.configuracion import KeycloakConfig
from domain.utils.seguridad import sanitizar_log

_portador = HTTPBearer(auto_error=False)
_log = logging.getLogger(__name__)

# Requiere opt-in explícito para deshabilitar auth (solo desarrollo local).
# Nunca debe estar en True en producción.
_AUTH_DESHABILITADA = os.getenv("PORTAL_AUTH_DISABLED", "").lower() == "true"

_jwks_cache: dict | None = None
_jwks_cache_ts: float = 0.0
_JWKS_TTL = 3600  # segundos — Keycloak rota claves raramente


class UsuarioPortalInterno:
    """Datos del operador autenticado extraídos del JWT de Keycloak."""

    def __init__(self, sub: str, email: str, roles: list[str]) -> None:
        self.sub = sub
        self.email = email
        self.roles = roles

    def tiene_rol(self, rol: str) -> bool:
        return rol in self.roles


def _obtener_config_keycloak(request: Request) -> KeycloakConfig:
    return request.app.state.config.keycloak


async def _obtener_jwks(config: KeycloakConfig) -> dict:
    global _jwks_cache, _jwks_cache_ts
    ahora = time.monotonic()
    if _jwks_cache is None or (ahora - _jwks_cache_ts) > _JWKS_TTL:
        async with httpx.AsyncClient() as client:
            respuesta = await client.get(config.jwks_uri, timeout=5)
            respuesta.raise_for_status()
            _jwks_cache = respuesta.json()
            _jwks_cache_ts = ahora
    return _jwks_cache


async def _decodificar_jwt(token: str, config: KeycloakConfig, request: Request) -> UsuarioPortalInterno:
    ip = request.client.host if request.client else "unknown"
    jwks = await _obtener_jwks(config)
    try:
        # El mapper "audience-portal" en el cliente Keycloak añade sagrilaft-portal
        # al claim aud del access token. python-jose acepta si el client_id está
        # contenido en aud aunque éste incluya también "account".
        # El azp (authorized party) se verifica adicionalmente abajo.
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=config.issuer,
            audience=config.client_id,
        )
    except JWTError as exc:
        _log.warning("AUTH_FAILED event=jwt_invalid ip=%s reason=%s", ip, sanitizar_log(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido o expirado: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    azp = payload.get("azp")
    if azp != config.client_id:
        _log.warning("AUTH_FAILED event=azp_mismatch ip=%s azp=%s", ip, sanitizar_log(azp))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token emitido para un cliente distinto.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # sub puede faltar si el cliente Keycloak no tiene el scope "basic" configurado.
    # Usamos preferred_username como fallback hasta que el scope esté correcto.
    sub = payload.get("sub") or payload.get("preferred_username", "")
    _log.info("AUTH_OK sub=%s ip=%s", sanitizar_log(sub), ip)
    return UsuarioPortalInterno(
        sub=sub,
        email=payload.get("email", ""),
        roles=payload.get("realm_access", {}).get("roles", []),
    )


async def portal_interno(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Security(_portador),
    keycloak: KeycloakConfig = Depends(_obtener_config_keycloak),
) -> UsuarioPortalInterno:
    """
    Dependency de FastAPI que protege rutas del portal interno.

    Uso sin acceder al usuario:
        @enrutador.get("/", dependencies=[Depends(portal_interno)])

    Uso accediendo al usuario autenticado:
        async def mi_endpoint(usuario: UsuarioPortalInterno = Depends(portal_interno)):
    """
    if not keycloak.configurado:
        if not _AUTH_DESHABILITADA:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "El servidor de autenticación no está configurado. "
                    "Contacte al administrador del sistema."
                ),
            )
        _log.warning(
            "PORTAL_AUTH_DISABLED=true — portal interno SIN AUTENTICACIÓN. "
            "Solo válido en desarrollo local."
        )
        return UsuarioPortalInterno(sub="dev", email="dev@localhost", roles=["acceso_clientes", "acceso_proveedores"])

    if credenciales is None:
        ip = request.client.host if request.client else "unknown"
        _log.warning("AUTH_FAILED event=no_token ip=%s path=%s", ip, sanitizar_log(request.url.path))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token Bearer de Keycloak",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _decodificar_jwt(credenciales.credentials, keycloak, request)
