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

from core import load_config
from database import engine, Base
from routers import formulario, validacion, listas_cautela
from domain.excepciones import (
    ContraparteInvalidaError,
    DocumentoNoEncontradoError,
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    FormularioNoEncontradoPorCredencialesError,
    FormularioYaEnviadoError,
)
from services.formulario.exportacion_pdf import DependenciaPdfNoInstaladaError
from infrastructure.ensamblaje import (
    crear_orquestador_validacion,
    crear_servicio_listas_cautela,
)

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
    from sqlalchemy import text
    columnas_nuevas = {
        'digito_verificacion':                  'TEXT',
        'realiza_operaciones_moneda_extranjera': 'TEXT',
        'paises_operaciones':                   'TEXT',
        'tipos_transaccion_otros':              'TEXT',
    }
    with engine.connect() as conn:
        columnas_existentes = {
            row[1] for row in conn.execute(text("PRAGMA table_info(formularios)"))
        }
        for columna, tipo in columnas_nuevas.items():
            if columna not in columnas_existentes:
                conn.execute(text(f"ALTER TABLE formularios ADD COLUMN {columna} {tipo}"))
                logger.info("Migración aplicada: columna '%s' agregada a 'formularios'", columna)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(formulario.enrutador)
app.include_router(validacion.enrutador)
app.include_router(listas_cautela.enrutador)

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


@app.exception_handler(FormularioNoEncontradoPorCredencialesError)
async def _formulario_no_encontrado_por_credenciales(
    _: Request,
    exc: FormularioNoEncontradoPorCredencialesError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ContraparteInvalidaError)
async def _contraparte_invalida(_: Request, exc: ContraparteInvalidaError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DocumentoNoEncontradoError)
async def _documento_no_encontrado(_: Request, __: DocumentoNoEncontradoError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Documento no encontrado"})


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
