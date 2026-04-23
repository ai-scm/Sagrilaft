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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.configuracion import AppConfig
from core import load_config
from core.limitador import limitador
from database import engine, Base
from routers import formulario, validacion, listas_cautela
from routers import acceso_manual
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
from services.formulario.exportacion_pdf import DependenciaPdfNoInstaladaError
from infrastructure.ensamblaje import (
    crear_orquestador_validacion,
    crear_servicio_listas_cautela,
)
from sqlalchemy import text


logging.basicConfig(level=logging.INFO)
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def _aplicar_migraciones(engine) -> None:
    """
    Aplica migraciones de columnas nuevas sin borrar datos existentes.

    SQLAlchemy create_all() no modifica tablas ya creadas, por lo que las
    columnas añadidas en versiones posteriores se agregan aquí con ALTER TABLE.
    Se registra cada migración para facilitar el seguimiento en logs.
    """
    columnas_nuevas_formularios = {
        'digito_verificacion':                  'TEXT',
        'realiza_operaciones_moneda_extranjera': 'TEXT',
        'paises_operaciones':                   'TEXT',
        'tipos_transaccion_otros':              'TEXT',
    }
    with engine.connect() as conn:
        columnas_existentes_formularios = {
            row[1] for row in conn.execute(text("PRAGMA table_info(formularios)"))
        }
        for columna, tipo in columnas_nuevas_formularios.items():
            if columna not in columnas_existentes_formularios:
                conn.execute(text(f"ALTER TABLE formularios ADD COLUMN {columna} {tipo}"))
                logger.info("Migración aplicada: columna '%s' agregada a 'formularios'", columna)

        columnas_existentes_accesos = {
            row[1] for row in conn.execute(text("PRAGMA table_info(accesos_manuales)"))
        }
        if "expires_at" not in columnas_existentes_accesos:
            conn.execute(text("ALTER TABLE accesos_manuales ADD COLUMN expires_at TEXT"))
            conn.execute(text("UPDATE accesos_manuales SET expires_at = datetime('now', '+30 days')"))
            logger.info("Migración aplicada: columna 'expires_at' agregada a 'accesos_manuales'")
        if "consumed_at" not in columnas_existentes_accesos:
            conn.execute(text("ALTER TABLE accesos_manuales ADD COLUMN consumed_at TEXT"))
            logger.info("Migración aplicada: columna 'consumed_at' agregada a 'accesos_manuales'")

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


app = FastAPI(
    title="SAGRILAFT API",
    description="API para el Sistema de Autocontrol de Riesgo de Lavado de Activos y Financiación del Terrorismo",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limitador
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=load_config().frontend_urls,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(formulario.enrutador)
app.include_router(validacion.enrutador)
app.include_router(listas_cautela.enrutador)
app.include_router(acceso_manual.enrutador)

# ─────────────────────────────────────────────────────────────────────────────
# Exception Handlers (Domain -> HTTP)
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(FormularioNoEncontradoError)
async def _formulario_no_encontrado(_: Request, __: FormularioNoEncontradoError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Formulario no encontrado"})


@app.exception_handler(FormularioNoEditableError)
async def _formulario_no_editable(_: Request, exc: FormularioNoEditableError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FormularioYaEnviadoError)
async def _formulario_ya_enviado(_: Request, __: FormularioYaEnviadoError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "El formulario asociado a esas credenciales ya fue enviado."},
    )


@app.exception_handler(ContraparteInvalidaError)
async def _contraparte_invalida(_: Request, exc: ContraparteInvalidaError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DocumentoNoEncontradoError)
async def _documento_no_encontrado(_: Request, __: DocumentoNoEncontradoError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Documento no encontrado"})


@app.exception_handler(CredencialesAccesoInvalidasError)
async def _credenciales_acceso_invalidas(
    _: Request, exc: CredencialesAccesoInvalidasError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
    )


@app.exception_handler(TokenDiligenciamientoInvalidoError)
async def _token_diligenciamiento_invalido(
    _: Request, exc: TokenDiligenciamientoInvalidoError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": "El enlace de diligenciamiento no es válido o ya expiró."},
    )


@app.exception_handler(AccesoExpiradoError)
async def _acceso_expirado(_: Request, exc: AccesoExpiradoError) -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={"detail": str(exc)},
    )


@app.exception_handler(PermissionError)
async def _permission_error(_: Request, exc: PermissionError) -> JSONResponse:
    # Tipicamente ocurre al escribir en disco (uploads) sin permisos.
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(DependenciaPdfNoInstaladaError)
async def _dependencia_pdf_no_instalada(_: Request, exc: DependenciaPdfNoInstaladaError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "hint": "Instala dependencias del backend (weasyprint + libs del sistema) para habilitar la exportación del PDF al radicar.",
        },
    )


@app.get("/")
def raiz():
    return {
        "servicio": "SAGRILAFT API",
        "version": "2.0.0",
        "estado": "activo",
        "modo_ia": "bedrock",
    }
