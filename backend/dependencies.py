"""
Funciones de dependencia (DI) centralizadas para los routers FastAPI.

SRP : único lugar donde se declaran y resuelven las dependencias compartidas.
DIP : los routers dependen de estas abstracciones en lugar de acceder a
      app.state directamente, desacoplando la infraestructura de los handlers.
"""

from fastapi import Request

from services.contracts import IExtractorIA
from services.document_orchestrator import OrquestadorValidacionDocumentos
from services.lista_cautela_service import ListaCautelaService


def obtener_extractor(solicitud: Request) -> IExtractorIA:
    """Obtiene el extractor IA registrado en el ciclo de vida de la aplicación."""
    return solicitud.app.state.orchestrator.extractor


def obtener_orquestador(solicitud: Request) -> OrquestadorValidacionDocumentos:
    """Obtiene el orquestador de validación documental registrado en app.state."""
    return solicitud.app.state.orchestrator


def obtener_servicio_lista_cautela(solicitud: Request) -> ListaCautelaService:
    """Obtiene el servicio de listas de cautela registrado en app.state."""
    return solicitud.app.state.lista_cautela_service
