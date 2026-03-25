"""
Funciones de dependencia (DI) centralizadas para los routers FastAPI.

SRP: un único lugar donde se declaran las dependencias compartidas.
"""

from fastapi import Request

from services.contracts import IAIExtractor


def get_extractor(request: Request) -> IAIExtractor:
    """Obtiene el extractor IA inyectado en app.state."""
    return request.app.state.orchestrator.extractor


def get_orchestrator(request: Request):
    """Obtiene el orquestador de validación inyectado en app.state."""
    return request.app.state.orchestrator
