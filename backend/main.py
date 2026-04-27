"""
SAGRILAFT API — Punto de entrada principal.

Configura inyección de dependencias para el extractor IA (Bedrock)
y registra todos los validadores de documentos.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from models import _sumar_dias_habiles, _DIAS_HABILES_VIGENCIA_ACCESO

from core import load_config
from core.limitador import limitador
from database import engine, Base
from domain.excepciones import (
    AccesoExpiradoError,
    ContraparteInvalidaError,
    CredencialesAccesoInvalidasError,
    DocumentoNoEncontradoError,
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    FormularioYaEnviadoError,
    TokenDiligenciamientoInvalidoError,
)
from infrastructure.ensamblaje import crear_orquestador_validacion, crear_servicio_listas_cautela
from routers import acceso_manual, formulario, listas_cautela, validacion
from services.formulario.exportacion_pdf import DependenciaPdfNoInstaladaError


logging.basicConfig(level=logging.INFO)
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_NOMBRE_SERVICIO = "SAGRILAFT API"
_VERSION_SERVICIO = "2.0.0"


def _respuesta_error(status_code: int, detalle: str, *, hint: str | None = None) -> JSONResponse:
    contenido = {"detail": detalle}
    if hint is not None:
        contenido["hint"] = hint
    return JSONResponse(status_code=status_code, content=contenido)


def _respuesta_error_desde_excepcion(status_code: int, exc: Exception) -> JSONResponse:
    return _respuesta_error(status_code, str(exc))


def _obtener_columnas_existentes(conn, tabla: str) -> set[str]:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({tabla})"))}


def _agregar_columna_si_falta(
    conn,
    tabla: str,
    columna: str,
    tipo: str,
    *,
    columnas_existentes: set[str] | None = None,
) -> bool:
    existentes = columnas_existentes or _obtener_columnas_existentes(conn, tabla)
    if columna in existentes:
        return False
    conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
    logger.info("Migración aplicada: columna '%s' agregada a '%s'", columna, tabla)
    return True


def _migrar_formularios(conn) -> None:
    columnas_nuevas_formularios = {
        "digito_verificacion": "TEXT",
        "realiza_operaciones_moneda_extranjera": "TEXT",
        "paises_operaciones": "TEXT",
        "tipos_transaccion_otros": "TEXT",
    }
    columnas_existentes = _obtener_columnas_existentes(conn, "formularios")
    for columna, tipo in columnas_nuevas_formularios.items():
        _agregar_columna_si_falta(
            conn,
            "formularios",
            columna,
            tipo,
            columnas_existentes=columnas_existentes,
        )


def _migrar_accesos_manuales(conn) -> None:
    columnas_existentes = _obtener_columnas_existentes(conn, "accesos_manuales")

    expires_at_agregada = _agregar_columna_si_falta(
        conn,
        "accesos_manuales",
        "expires_at",
        "TEXT",
        columnas_existentes=columnas_existentes,
    )
    _agregar_columna_si_falta(
        conn,
        "accesos_manuales",
        "consumed_at",
        "TEXT",
        columnas_existentes=columnas_existentes,
    )

    if expires_at_agregada:
        nueva_fecha = _sumar_dias_habiles(datetime.now(timezone.utc), _DIAS_HABILES_VIGENCIA_ACCESO)
        conn.execute(text("UPDATE accesos_manuales SET expires_at = :f"), {"f": nueva_fecha.isoformat()})


def _aplicar_migraciones(engine) -> None:
    """
    Aplica migraciones de columnas nuevas sin borrar datos existentes.

    SQLAlchemy create_all() no modifica tablas ya creadas, por lo que las
    columnas añadidas en versiones posteriores se agregan aquí con ALTER TABLE.
    Se registra cada migración para facilitar el seguimiento en logs.
    """
    with engine.connect() as conn:
        _migrar_formularios(conn)
        _migrar_accesos_manuales(conn)
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: inicialización y limpieza de la aplicación."""
    config = load_config()
    Base.metadata.create_all(bind=engine)
    _aplicar_migraciones(engine)

    app.state.orchestrator = crear_orquestador_validacion(config)
    app.state.config = config
    app.state.servicio_listas_cautela = crear_servicio_listas_cautela()

    logger.info("SAGRILAFT API iniciada")
    yield
    logger.info("SAGRILAFT API detenida")


def _registrar_rutas(app: FastAPI) -> None:
    app.include_router(formulario.enrutador)
    app.include_router(validacion.enrutador)
    app.include_router(listas_cautela.enrutador)
    app.include_router(acceso_manual.enrutador)


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

    app.add_exception_handler(FormularioNoEncontradoError, handler(404, "Formulario no encontrado"))
    app.add_exception_handler(FormularioNoEditableError, handler_from_exception(400))
    app.add_exception_handler(
        FormularioYaEnviadoError,
        handler(409, "El formulario asociado a esas credenciales ya fue enviado."),
    )
    app.add_exception_handler(ContraparteInvalidaError, handler_from_exception(422))
    app.add_exception_handler(DocumentoNoEncontradoError, handler(404, "Documento no encontrado"))
    app.add_exception_handler(CredencialesAccesoInvalidasError, handler_from_exception(401))
    app.add_exception_handler(TokenDiligenciamientoInvalidoError, handler_from_exception(404))
    app.add_exception_handler(AccesoExpiradoError, handler_from_exception(410))
    app.add_exception_handler(PermissionError, handler_from_exception(500))
    app.add_exception_handler(
        DependenciaPdfNoInstaladaError,
        handler_from_exception_with_hint(
            500,
            hint="Instala dependencias del backend (weasyprint + libs del sistema) para habilitar la exportación del PDF al radicar.",
        ),
    )


def _configurar_middlewares(app: FastAPI) -> None:
    # Se mantiene el comportamiento original: `load_config()` se evalúa al crear la app.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=load_config().frontend_urls,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _crear_app() -> FastAPI:
    app = FastAPI(
        title=_NOMBRE_SERVICIO,
        description="API para el Sistema de Autocontrol de Riesgo de Lavado de Activos y Financiación del Terrorismo",
        version=_VERSION_SERVICIO,
        lifespan=lifespan,
    )

    app.state.limiter = limitador
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    _configurar_middlewares(app)
    _registrar_rutas(app)
    _registrar_manejadores_excepcion(app)

    @app.get("/")
    def raiz():
        return {
            "servicio": _NOMBRE_SERVICIO,
            "version": _VERSION_SERVICIO,
            "estado": "activo",
            "modo_ia": "bedrock",
        }

    return app


app = _crear_app()
