"""
Fábricas de adaptadores de infraestructura para inyección de dependencias.

Responsabilidad acotada: exponer repositorios SQLAlchemy y objetos de app.state
(config, extractor IA). Las fábricas de servicios de aplicación viven en
api/dependencies.py, que es el punto de composición de la capa API.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from domain.contratos import ExtractorIAImp
from domain.puertos.almacenamiento import IAlmacenamiento
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.repositorios import (
    RepositorioAccesoManual,
    RepositorioDocumento,
    RepositorioExpediente,
    RepositorioFirma,
    RepositorioFormulario,
    RepositorioValidacion,
)
from infrastructure.configuracion import AppConfig
from infrastructure.persistencia.auditoria_repositorio import RepositorioAuditoriaSQLAlchemy
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


def obtener_storage(solicitud: Request) -> IAlmacenamiento:
    """Obtiene el backend de almacenamiento registrado en el ciclo de vida."""
    return solicitud.app.state.storage


def obtener_extractor(solicitud: Request) -> ExtractorIAImp:
    """Obtiene el extractor IA registrado en el ciclo de vida de la aplicación."""
    return solicitud.app.state.orchestrator.extractor


# ── Factories de repositorios ────────────────────────────────────────────────
# Todas dependen de get_db (request-scoped), de modo que instancias creadas en
# el mismo request comparten la misma Session → atomicidad transaccional preservada.
# Los tipos de retorno declaran el puerto (Protocol) — no la clase SQLAlchemy concreta.

def obtener_repo_formulario(
    sesion: Session = Depends(get_db),
) -> RepositorioFormulario:
    return RepositorioFormularioSQLAlchemy(sesion)


def obtener_repo_documento(
    sesion: Session = Depends(get_db),
) -> RepositorioDocumento:
    return RepositorioDocumentoSQLAlchemy(sesion)


def obtener_repo_validacion(
    sesion: Session = Depends(get_db),
) -> RepositorioValidacion:
    return RepositorioValidacionSQLAlchemy(sesion)


def obtener_repo_expediente(
    sesion: Session = Depends(get_db),
) -> RepositorioExpediente:
    return RepositorioExpedienteSQLAlchemy(sesion)


def obtener_repo_firma(
    sesion: Session = Depends(get_db),
) -> RepositorioFirma:
    return RepositorioFirmaSQLAlchemy(sesion)


def obtener_repo_acceso(
    sesion: Session = Depends(get_db),
) -> RepositorioAccesoManual:
    return RepositorioAccesoManualSQLAlchemy(sesion)


def obtener_repo_auditoria(
    sesion: Session = Depends(get_db),
) -> RepositorioAuditoria:
    return RepositorioAuditoriaSQLAlchemy(sesion)
