"""
Middleware de autenticacion - Keycloak.

Valida tokens JWT emitidos por Keycloak contra las claves publicas JWKS.
Las claves se cachean durante un periodo configurable para reducir llamadas
al servidor de identidad.

Rutas protegidas por `portal_interno`:
  - Todos los endpoints de /api/expedientes/*
  - POST /api/accesos-manuales/         (crear acceso)
  - GET  /api/accesos-manuales/         (listar accesos)

Rutas publicas (sin esta dependency):
  - POST /api/formularios/*                       (acceso por token de tercero)
  - POST /api/webhooks/*                          (callbacks Zoho Sign - autenticados por HMAC)
  - GET  /api/accesos-manuales/token/{token}      (enlace externo al destinatario)
"""

import logging
import os
import sys
import time

import httpx
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from infrastructure.configuracion import KeycloakConfig
from domain.utils.seguridad import sanitizar_log

_portador = HTTPBearer(auto_error=False)
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# A07:2025 - Fix 1 (CWE-287): bloquear bypass de autenticacion en produccion.
# ---------------------------------------------------------------------------
_AUTH_DESHABILITADA = os.getenv("PORTAL_AUTH_DISABLED", "").lower() == "true"
_APP_ENV = os.getenv("APP_ENV", "production").lower()

if _AUTH_DESHABILITADA and _APP_ENV not in ("development", "local", "test"):
    _log.critical(
        "SECURITY_ABORT PORTAL_AUTH_DISABLED=true detectado en APP_ENV=%s - "
        "el bypass de autenticacion no esta permitido en este entorno. Abortando.",
        _APP_ENV,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# A07:2025 - Fix 3 (CWE-307): contador de fallos por IP.
# ---------------------------------------------------------------------------
_fallos_por_ip: dict[str, list[float]] = {}
_FALLOS_VENTANA = 300   # segundos (ventana deslizante de 5 minutos)
_FALLOS_UMBRAL = 10     # intentos fallidos antes de emitir alerta


def _registrar_fallo_ip(ip: str) -> None:
    """Registra un intento fallido y alerta si se supera el umbral."""
    ahora = time.monotonic()
    historial = _fallos_por_ip.setdefault(ip, [])
    historial.append(ahora)
    _fallos_por_ip[ip] = [t for t in historial if ahora - t <= _FALLOS_VENTANA]
    total = len(_fallos_por_ip[ip])
    if total >= _FALLOS_UMBRAL:
        _log.error(
            "AUTH_ALERT event=brute_force_suspected ip=%s fallos=%d ventana=%ds",
            ip,
            total,
            _FALLOS_VENTANA,
        )


# ---------------------------------------------------------------------------
# A02:2025 - Security Misconfiguration: JWKS TTL configurable.
# ---------------------------------------------------------------------------
_jwks_cache: dict | None = None
_jwks_cache_ts: float = 0.0
# A02:2025 - TTL configurable para reducir ventana de riesgo ante rotacion de claves.
# Default: 300s (5 min) en lugar de 3600s (1 hora) hardcoded.
_JWKS_TTL = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "300"))


class UsuarioPortalInterno:
    """Datos del operador autenticado extraidos del JWT de Keycloak."""

    def __init__(self, sub: str, email: str, roles: list[str]) -> None:
        self.sub = sub
        self.email = email
        self.roles = roles

    def tiene_rol(self, rol: str) -> bool:
        return rol in self.roles


def _obtener_config_keycloak(request: Request) -> KeycloakConfig:
    return request.app.state.config.keycloak


async def _obtener_jwks(config: KeycloakConfig) -> dict:
    """
    Obtiene las claves publicas JWKS de Keycloak con manejo de errores.
    
    A10:2025 - Manejo de excepciones:
    - Si la red falla pero existe cache stale, se usa como fallback (graceful degradation).
    - Si no hay cache disponible, se retorna 503 con mensaje claro al cliente.
    - Todas las excepciones HTTP se loguean con contexto para troubleshooting.
    """
    global _jwks_cache, _jwks_cache_ts
    ahora = time.monotonic()
    
    if _jwks_cache is None or (ahora - _jwks_cache_ts) > _JWKS_TTL:
        try:
            async with httpx.AsyncClient() as client:
                respuesta = await client.get(config.jwks_uri, timeout=5)
                respuesta.raise_for_status()
                _jwks_cache = respuesta.json()
                _jwks_cache_ts = ahora
                _log.debug("JWKS_REFRESH_OK uri=%s", config.jwks_uri)
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            # A10:2025 - Graceful degradation: si existe cache stale, usarlo como fallback
            if _jwks_cache is not None:
                edad_cache = ahora - _jwks_cache_ts
                _log.warning(
                    "JWKS_REFRESH_FAILED uri=%s reason=%s usando_cache_stale=true edad_cache=%.0fs",
                    config.jwks_uri,
                    sanitizar_log(str(exc)),
                    edad_cache,
                )
                return _jwks_cache
            
            # Sin cache disponible: fallo critico
            _log.error(
                "JWKS_UNAVAILABLE uri=%s reason=%s cache_disponible=false",
                config.jwks_uri,
                sanitizar_log(str(exc)),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de autenticacion no disponible temporalmente. Intente nuevamente.",
            ) from exc
    
    return _jwks_cache


async def _decodificar_jwt(token: str, config: KeycloakConfig, request: Request) -> UsuarioPortalInterno:
    ip = request.client.host if request.client else "unknown"
    # A09:2025 - CWE-117: sanitizar user-agent y path para prevenir log injection
    user_agent = sanitizar_log(request.headers.get("user-agent", "unknown"))
    path = sanitizar_log(request.url.path)
    
    jwks = await _obtener_jwks(config)
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=config.issuer,
            audience=config.client_id,
        )
    except JWTError as exc:
        _registrar_fallo_ip(ip)
        # A09:2025 - CWE-778: logs con contexto suficiente para analisis forense
        _log.warning(
            "AUTH_FAILED event=jwt_invalid ip=%s path=%s user_agent=%s reason=%s",
            ip,
            path,
            user_agent,
            sanitizar_log(type(exc).__name__),
        )
        # A09:2025 - CWE-532: mensaje generico al cliente, detalle solo en logs
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    azp = payload.get("azp")
    if azp != config.client_id:
        _registrar_fallo_ip(ip)
        _log.warning(
            "AUTH_FAILED event=azp_mismatch ip=%s path=%s azp=%s expected=%s",
            ip,
            path,
            sanitizar_log(azp),
            sanitizar_log(config.client_id),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token emitido para un cliente distinto.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # A07:2025 - Fix 2 (CWE-287): claim `sub` es obligatorio.
    sub = payload.get("sub")
    if not sub:
        _registrar_fallo_ip(ip)
        _log.warning(
            "AUTH_FAILED event=missing_sub ip=%s path=%s",
            ip,
            path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido: identificador de usuario ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles = payload.get("realm_access", {}).get("roles", [])
    # A09:2025 - CWE-778: logs de autenticacion exitosa con contexto completo
    _log.info(
        "AUTH_OK sub=%s ip=%s path=%s roles=%s user_agent=%s",
        sanitizar_log(sub),
        ip,
        path,
        roles,
        user_agent,
    )
    return UsuarioPortalInterno(
        sub=sub,
        email=payload.get("email", ""),
        roles=roles,
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
                    "El servidor de autenticacion no esta configurado. "
                    "Contacte al administrador del sistema."
                ),
            )
        _log.warning(
            "PORTAL_AUTH_DISABLED=true - portal interno SIN AUTENTICACION. "
            "Solo valido en desarrollo local."
        )
        return UsuarioPortalInterno(
            sub="dev",
            email="dev@localhost",
            roles=["acceso_clientes", "acceso_proveedores"],
        )

    if credenciales is None:
        ip = request.client.host if request.client else "unknown"
        path = sanitizar_log(request.url.path)
        _registrar_fallo_ip(ip)
        _log.warning(
            "AUTH_FAILED event=no_token ip=%s path=%s",
            ip,
            path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token Bearer de Keycloak.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await _decodificar_jwt(credenciales.credentials, keycloak, request)


# ---------------------------------------------------------------------------
# A01:2025 - Broken Access Control: dependency factory para RBAC.
# ---------------------------------------------------------------------------
def requiere_rol(*roles_permitidos: str):
    """
    Dependency factory para control de acceso basado en roles (RBAC).
    
    Implementa deny-by-default: si el usuario no tiene NINGUNO de los roles
    permitidos, se rechaza con 403 Forbidden.
    
    Uso:
        @enrutador.get("/clientes", dependencies=[Depends(requiere_rol("acceso_clientes"))])
        
        async def listar_clientes(usuario = Depends(requiere_rol("acceso_clientes"))):
            ...
    """
    async def _verificar_autorizacion(
        usuario: UsuarioPortalInterno = Depends(portal_interno),
    ) -> UsuarioPortalInterno:
        if not any(usuario.tiene_rol(rol) for rol in roles_permitidos):
            roles_str = ", ".join(roles_permitidos)
            # A09:2025 - CWE-778: logs de fallos de autorizacion para auditoria
            _log.warning(
                "AUTHZ_FAILED sub=%s roles_requeridos=[%s] roles_usuario=%s",
                sanitizar_log(usuario.sub),
                roles_str,
                usuario.roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de: {roles_str}",
            )
        return usuario

    return _verificar_autorizacion
