"""
SAGRILAFT API — Punto de entrada principal.

Configura inyección de dependencias para el extractor IA (Bedrock)
y registra todos los validadores de documentos.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import load_config
from database import engine, Base
from routers import formulario, validacion, listas_cautela
from services.listas.servicio_listas_cautela import ListaCautelaService
from services.listas.proveedores_simulados import PROVEEDORES_SIMULADOS
from services.extractores.bedrock_extractor import ExtractorBedrock
from services.orquestacion.orquestador_documentos import OrquestadorValidacionDocumentos
from services.validators.camara_comercio import ValidadorCamaraComercio
from services.validators.cruzado import ValidadorCruzadoDocumentos, REGLAS_CRUCE_PREDETERMINADAS
from services.validators.rut import ValidadorRut
from services.validators.estados_financieros import ValidadorEstadosFinancieros
from services.validators.cedula import ValidadorCedula
from services.validators.referencia_bancaria import ValidadorReferenciaBancaria

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _crear_extractor(config) -> ExtractorBedrock:
    """Fábrica: crea el extractor Bedrock con las credenciales configuradas."""
    logger.info(
        "Usando extractor Bedrock (región=%s, modelo=%s)",
        config.aws.region, config.aws.model_id
    )
    return ExtractorBedrock(
        region=config.aws.region,
        modelo_id=config.aws.model_id,
        max_tokens=config.aws.max_tokens,
    )


def _crear_orquestador(config) -> OrquestadorValidacionDocumentos:
    """Fábrica: crea y configura el orquestador con todos los validadores."""
    extractor = _crear_extractor(config)
    validador_cruzado = ValidadorCruzadoDocumentos(REGLAS_CRUCE_PREDETERMINADAS)
    orquestador = OrquestadorValidacionDocumentos(extractor, validador_cruzado)

    # Registrar validadores (OCP: agregar nuevos aquí sin tocar más código)
    orquestador.registrar_validador(ValidadorCamaraComercio())
    orquestador.registrar_validador(ValidadorRut())
    orquestador.registrar_validador(ValidadorEstadosFinancieros())
    orquestador.registrar_validador(ValidadorCedula())
    orquestador.registrar_validador(ValidadorReferenciaBancaria())

    logger.info(
        "Validadores registrados: %s",
        ", ".join(orquestador.tipos_registrados)
    )
    return orquestador


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: inicialización y limpieza de la aplicación."""
    config = load_config()

    Base.metadata.create_all(bind=engine)

    app.state.orchestrator = _crear_orquestador(config)
    app.state.config = config
    app.state.servicio_listas_cautela = ListaCautelaService(PROVEEDORES_SIMULADOS)

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


@app.get("/")
def raiz():
    return {
        "servicio": "SAGRILAFT API",
        "version": "2.0.0",
        "estado": "activo",
        "modo_ia": "bedrock",
    }
