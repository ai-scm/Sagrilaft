"""
Funciones de dependencia (DI) centralizadas para los routers FastAPI.

SRP : único lugar donde se declaran y resuelven las dependencias compartidas.
DIP : los routers dependen de estas abstracciones en lugar de acceder a
      app.state directamente, desacoplando la infraestructura de los handlers.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from infrastructure.configuracion import AppConfig
from domain.contratos import ExtractorIAImp
from infrastructure.persistencia.database import get_db
from infrastructure.persistencia.repositorios import (
    RepositorioAccesoManualSQLAlchemy,
    RepositorioDocumentoSQLAlchemy,
    RepositorioExpedienteSQLAlchemy,
    RepositorioFirmaSQLAlchemy,
    RepositorioFormularioSQLAlchemy,
    RepositorioValidacionSQLAlchemy,
)
from services.validacion.orquestador import OrquestadorValidacionDocumentos
from services.listas.servicio_listas_cautela import ListaCautelaService


def obtener_config(solicitud: Request) -> AppConfig:
    """Obtiene la configuración registrada en el ciclo de vida de la aplicación."""
    return solicitud.app.state.config


def obtener_extractor(solicitud: Request) -> ExtractorIAImp:
    """Obtiene el extractor IA registrado en el ciclo de vida de la aplicación."""
    return solicitud.app.state.orchestrator.extractor


def obtener_orquestador(solicitud: Request) -> OrquestadorValidacionDocumentos:
    """Obtiene el orquestador de validación documental registrado en app.state."""
    return solicitud.app.state.orchestrator


def obtener_servicio_lista_cautela(solicitud: Request) -> ListaCautelaService:
    """Obtiene el servicio de listas de cautela registrado en app.state."""
    return solicitud.app.state.servicio_listas_cautela


# ── Factories de repositorios ────────────────────────────────────────────────
# Todas dependen de get_db (request-scoped), de modo que instancias creadas en
# el mismo request comparten la misma Session → atomicidad transaccional preservada.

def obtener_repo_formulario(
    sesion: Session = Depends(get_db),
) -> RepositorioFormularioSQLAlchemy:
    return RepositorioFormularioSQLAlchemy(sesion)


def obtener_repo_documento(
    sesion: Session = Depends(get_db),
) -> RepositorioDocumentoSQLAlchemy:
    return RepositorioDocumentoSQLAlchemy(sesion)


def obtener_repo_validacion(
    sesion: Session = Depends(get_db),
) -> RepositorioValidacionSQLAlchemy:
    return RepositorioValidacionSQLAlchemy(sesion)


def obtener_repo_expediente(
    sesion: Session = Depends(get_db),
) -> RepositorioExpedienteSQLAlchemy:
    return RepositorioExpedienteSQLAlchemy(sesion)


def obtener_repo_firma(
    sesion: Session = Depends(get_db),
) -> RepositorioFirmaSQLAlchemy:
    return RepositorioFirmaSQLAlchemy(sesion)


def obtener_repo_acceso(
    sesion: Session = Depends(get_db),
) -> RepositorioAccesoManualSQLAlchemy:
    return RepositorioAccesoManualSQLAlchemy(sesion)
