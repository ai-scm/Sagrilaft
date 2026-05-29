"""
SAGRILAFT API — Punto de entrada principal.

Configura inyección de dependencias para el extractor IA (Bedrock)
y registra todos los validadores de documentos.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from infrastructure.configuracion import load_config
from infrastructure.storage.backend import crear_storage
from api.limitador import limitador
from domain.excepciones import (
    AccesoExpiradoError,
    ContraparteInvalidaError,
    CredencialesAccesoInvalidasError,
    DocumentoNoEncontradoError,
    FirmaNoDisponibleError,
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    FormularioYaEnviadoError,
    SinPermisoError,
    TokenConsumidoError,
    TokenDiligenciamientoInvalidoError,
    WebhookTokenInvalidoError,
)
from infrastructure.ensamblaje import crear_orquestador_validacion, crear_servicio_listas_cautela
from api.routers import acceso_manual, auditoria, expedientes, formulario, listas_cautela, validacion, webhooks
from services.formulario.exportacion_pdf import DependenciaPdfNoInstaladaError
from infrastructure.zoho_sign.zoho_sign_service import ZohoSignService


logging.basicConfig(level=logging.INFO)
_log_seg = logging.getLogger("sagrilaft.security")
for _nombre in ("fontTools", "fontTools.ttLib", "fontTools.ttLib.ttFont",
                "fontTools.subset", "fontTools.subset.timer", "weasyprint"):
    logging.getLogger(_nombre).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_NOMBRE_SERVICIO = "SAGRILAFT API"
_VERSION_SERVICIO = "2.0.0"
_ESTADO = 'activo'
_MODO_IA = 'bedrock'

def _respuesta_error(status_code: int, detalle: str, *, hint: str | None = None) -> JSONResponse:
    contenido = {"detail": detalle}
    if hint is not None:
        contenido["hint"] = hint
    return JSONResponse(status_code=status_code, content=contenido)


def _respuesta_error_desde_excepcion(status_code: int, exc: Exception) -> JSONResponse:
    return _respuesta_error(status_code, str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: inicialización y limpieza de la aplicación."""
    config = load_config()

    config.zoho_sign.validar()

    app.state.storage = crear_storage(
        upload_dir=config.upload_dir,
        backend=config.storage_backend,
        s3_bucket=config.s3.bucket,
        s3_region=config.aws.region,
    )
    app.state.orchestrator            = crear_orquestador_validacion(config)
    app.state.config                  = config
    app.state.servicio_listas_cautela = crear_servicio_listas_cautela()
    app.state.zoho_sign               = ZohoSignService(config.zoho_sign)

    logger.info("SAGRILAFT API iniciada")
    yield
    logger.info("SAGRILAFT API detenida")


def _registrar_rutas(app: FastAPI) -> None:
    app.include_router(formulario.enrutador)
    app.include_router(validacion.enrutador)
    app.include_router(listas_cautela.enrutador)
    app.include_router(acceso_manual.enrutador)
    app.include_router(expedientes.enrutador)
    app.include_router(webhooks.enrutador)
    app.include_router(auditoria.enrutador)


def _registrar_manejadores_excepcion(app: FastAPI) -> None:
    def handler(status_code: int, detalle: str, *, hint: str | None = None):
        def _inner(_: Request, __: Exception) -> JSONResponse:
            return _respuesta_error(status_code, detalle, hint=hint)

        return _inner

    def handler_from_exception(status_code: int):
        def _inner(_: Request, exc: Exception) -> JSONResponse:
            return _respuesta_error_desde_excepcion(status_code, exc)

        return _inner

    def handler_from_exception_with_hint(status_code: int, *, hint: str):
        def _inner(_: Request, exc: Exception) -> JSONResponse:
            return _respuesta_error(status_code, str(exc), hint=hint)

        return _inner

    def _ip(req: Request) -> str:
        return req.client.host if req.client else "unknown"

    def handler_seguridad(status_code: int, evento: str, detalle: str):
        def _inner(req: Request, exc: Exception) -> JSONResponse:
            _log_seg.warning("SECURITY event=%s ip=%s path=%s", evento, _ip(req), req.url.path)
            return _respuesta_error(status_code, detalle)
        return _inner

    def handler_seguridad_from_exception(status_code: int, evento: str):
        def _inner(req: Request, exc: Exception) -> JSONResponse:
            _log_seg.warning("SECURITY event=%s ip=%s path=%s", evento, _ip(req), req.url.path)
            return _respuesta_error_desde_excepcion(status_code, exc)
        return _inner

    app.add_exception_handler(SinPermisoError,             handler_seguridad(403, "ACCESS_DENIED", "Acceso denegado"))
    app.add_exception_handler(CredencialesAccesoInvalidasError, handler_seguridad_from_exception(401, "CREDENTIALS_INVALID"))
    app.add_exception_handler(WebhookTokenInvalidoError,   handler_seguridad(403, "WEBHOOK_TOKEN_INVALID", "Token de webhook inválido"))
    app.add_exception_handler(FormularioNoEncontradoError, handler(404, "Formulario no encontrado"))
    app.add_exception_handler(FormularioNoEditableError, handler_from_exception(400))
    app.add_exception_handler(
        FormularioYaEnviadoError,
        handler(409, "El formulario asociado a esas credenciales ya fue enviado."),
    )
    app.add_exception_handler(ContraparteInvalidaError, handler_from_exception(422))
    app.add_exception_handler(DocumentoNoEncontradoError, handler(404, "Documento no encontrado"))
    app.add_exception_handler(FirmaNoDisponibleError, handler(404, "Documento firmado no disponible"))
    app.add_exception_handler(TokenDiligenciamientoInvalidoError, handler_from_exception(404))
    app.add_exception_handler(TokenConsumidoError,                handler_from_exception(410))
    app.add_exception_handler(AccesoExpiradoError,                handler_from_exception(410))
    app.add_exception_handler(
        DependenciaPdfNoInstaladaError,
        handler_from_exception_with_hint(
            500,
            hint="Instala dependencias del backend (weasyprint + libs del sistema) para habilitar la exportación del PDF al radicar.",
        ),
    )


def _configurar_middlewares(app: FastAPI) -> None:
    # Se mantiene el comportamiento original: `load_config()` se evalúa al crear la app.
    #TENER EN CUENTA EN DESPLIEGUE Y PRODUCCION.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=load_config().frontend_urls,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )


def _crear_app() -> FastAPI:
    app = FastAPI(
        title=_NOMBRE_SERVICIO,
        description="API para el Sistema de Autocontrol de Riesgo de Lavado de Activos y Financiación del Terrorismo",
        version=_VERSION_SERVICIO,
        lifespan=lifespan,
    )

    def _handler_rate_limit(req: Request, exc: RateLimitExceeded) -> JSONResponse:
        _log_seg.warning("SECURITY event=RATE_LIMIT_EXCEEDED ip=%s path=%s", req.client and req.client.host, req.url.path)
        return JSONResponse(status_code=429, content={"detail": "Demasiadas solicitudes. Intente más tarde."})

    app.state.limiter = limitador
    app.add_exception_handler(RateLimitExceeded, _handler_rate_limit)

    _configurar_middlewares(app)
    _registrar_rutas(app)
    _registrar_manejadores_excepcion(app)

    @app.get("/")
    def raiz():
        return {
            "servicio": _NOMBRE_SERVICIO,
            "version": _VERSION_SERVICIO,
            "estado": _ESTADO,
            "modo_ia": _MODO_IA,
        }

    return app


app = _crear_app()
