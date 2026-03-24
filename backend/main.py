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
from services.bedrock_extractor import BedrockExtractor
from services.document_orchestrator import DocumentValidationOrchestrator
from services.validators.camara_comercio import CamaraComercioValidator
from services.validators.rut import RutValidator
from services.validators.estados_financieros import EstadosFinancierosValidator
from services.validators.cedula import CedulaValidator
from services.validators.referencia_bancaria import ReferenciaBancariaValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _create_extractor(config):
    """Factory: crea el extractor Bedrock con las credenciales configuradas."""
    logger.info(
        "Usando extractor Bedrock (región=%s, modelo=%s)",
        config.aws.region, config.aws.model_id
    )
    return BedrockExtractor(
        region=config.aws.region,
        model_id=config.aws.model_id,
        max_tokens=config.aws.max_tokens,
    )


def _create_orchestrator(config) -> DocumentValidationOrchestrator:
    """Factory: crea y configura el orquestador con todos los validadores."""
    extractor = _create_extractor(config)
    orchestrator = DocumentValidationOrchestrator(extractor)

    # Registrar validadores (Open/Closed: agregar nuevos aquí sin tocar más código)
    orchestrator.register_validator(CamaraComercioValidator())
    orchestrator.register_validator(RutValidator())
    orchestrator.register_validator(EstadosFinancierosValidator())
    orchestrator.register_validator(CedulaValidator())
    orchestrator.register_validator(ReferenciaBancariaValidator())

    logger.info(
        "Validadores registrados: %s",
        ", ".join(orchestrator.registered_types)
    )
    return orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: inicialización y limpieza."""
    config = load_config()

    # Crear tablas
    Base.metadata.create_all(bind=engine)

    # Inyectar orquestador en app.state (DI pobre pero simple)
    app.state.orchestrator = _create_orchestrator(config)
    app.state.config = config

    logger.info("✅ SAGRILAFT API iniciada")
    yield
    logger.info("🛑 SAGRILAFT API detenida")


app = FastAPI(
    title="SAGRILAFT API",
    description="API para el Sistema de Autocontrol de Riesgo de Lavado de Activos y Financiación del Terrorismo",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(formulario.router)
app.include_router(validacion.router)
app.include_router(listas_cautela.router)


@app.get("/")
def root():
    return {
        "service": "SAGRILAFT API",
        "version": "2.0.0",
        "status": "running",
        "ai_mode": "bedrock",
    }
