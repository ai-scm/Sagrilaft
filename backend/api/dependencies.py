"""
Punto de composición de la capa API.

Único lugar donde los routers resuelven sus dependencias. Expone exclusivamente
servicios de aplicación — los routers no importan nada de infrastructure directamente.

Diseño:
  - Las fábricas de repositorios (infraestructura) viven en infrastructure/dependencies.py.
  - Este módulo las consume y las envuelve en servicios de aplicación listos para usar.
  - Los routers dependen solo de api.dependencies, api.schemas y domain.* (tipos).
"""

from fastapi import Depends, Request

from domain.contratos import ExtractorIAImp
from infrastructure.configuracion import AppConfig
from infrastructure.dependencies import (
    obtener_config,
    obtener_extractor,
    obtener_repo_acceso,
    obtener_repo_documento,
    obtener_repo_expediente,
    obtener_repo_firma,
    obtener_repo_formulario,
    obtener_repo_validacion,
)
from infrastructure.notificaciones.email_service import EmailService
from infrastructure.persistencia.repositorios import (
    RepositorioAccesoManualSQLAlchemy,
    RepositorioDocumentoSQLAlchemy,
    RepositorioExpedienteSQLAlchemy,
    RepositorioFirmaSQLAlchemy,
    RepositorioFormularioSQLAlchemy,
    RepositorioValidacionSQLAlchemy,
)
from services.acceso_manual.acceso_manual_service import AccesoManualService
from services.expedientes.expediente_service import ExpedienteService
from services.firma.firma_service import FirmaService
from services.formulario.formulario_service import FormularioService
from services.listas.servicio_listas_cautela import ListaCautelaService
from services.validacion.orquestador import OrquestadorValidacionDocumentos
from services.validacion.validacion_service import ValidacionService


# ── Estado global de la aplicación ──────────────────────────────────────────

def obtener_orquestador(solicitud: Request) -> OrquestadorValidacionDocumentos:
    """Obtiene el orquestador de validación documental registrado en app.state."""
    return solicitud.app.state.orchestrator


def obtener_servicio_lista_cautela(solicitud: Request) -> ListaCautelaService:
    """Obtiene el servicio de listas de cautela registrado en app.state."""
    return solicitud.app.state.servicio_listas_cautela


# ── Servicios de aplicación ──────────────────────────────────────────────────

def obtener_servicio_acceso(
    repo: RepositorioAccesoManualSQLAlchemy = Depends(obtener_repo_acceso),
    config: AppConfig = Depends(obtener_config),
) -> AccesoManualService:
    return AccesoManualService(repo, config.frontend_urls[0])


def obtener_servicio_email(
    config: AppConfig = Depends(obtener_config),
) -> EmailService:
    return EmailService(config.smtp)


def obtener_servicio_firma(
    request: Request,
    repo: RepositorioFirmaSQLAlchemy = Depends(obtener_repo_firma),
) -> FirmaService:
    config = request.app.state.config
    return FirmaService(
        repo=repo,
        zoho=request.app.state.zoho_sign,
        upload_dir=config.upload_dir,
        webhook_secret=config.zoho_sign.webhook_secret,
    )


def obtener_servicio_formulario(
    repo: RepositorioFormularioSQLAlchemy = Depends(obtener_repo_formulario),
    repo_doc: RepositorioDocumentoSQLAlchemy = Depends(obtener_repo_documento),
    extractor: ExtractorIAImp = Depends(obtener_extractor),
    config: AppConfig = Depends(obtener_config),
) -> FormularioService:
    return FormularioService(repo, repo_doc, extractor, config.upload_dir)


def obtener_servicio_expediente(
    repo: RepositorioExpedienteSQLAlchemy = Depends(obtener_repo_expediente),
) -> ExpedienteService:
    return ExpedienteService(repo)


def obtener_servicio_validacion(
    repo: RepositorioValidacionSQLAlchemy = Depends(obtener_repo_validacion),
    orquestador: OrquestadorValidacionDocumentos = Depends(obtener_orquestador),
    servicio_listas: ListaCautelaService = Depends(obtener_servicio_lista_cautela),
) -> ValidacionService:
    return ValidacionService(repo, orquestador, servicio_listas)
