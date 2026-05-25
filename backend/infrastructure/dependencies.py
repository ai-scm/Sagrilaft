"""
Fábricas de adaptadores de infraestructura para inyección de dependencias.

Responsabilidad acotada: exponer repositorios SQLAlchemy y objetos de app.state
(config, extractor IA). Las fábricas de servicios de aplicación viven en
api/dependencies.py, que es el punto de composición de la capa API.
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


def obtener_config(solicitud: Request) -> AppConfig:
    """Obtiene la configuración registrada en el ciclo de vida de la aplicación."""
    return solicitud.app.state.config


def obtener_extractor(solicitud: Request) -> ExtractorIAImp:
    """Obtiene el extractor IA registrado en el ciclo de vida de la aplicación."""
    return solicitud.app.state.orchestrator.extractor


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
