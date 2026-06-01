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
from domain.puertos.almacenamiento import IAlmacenamiento
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import (
    RepositorioAccesoManual,
    RepositorioDocumento,
    RepositorioExpediente,
    RepositorioFirma,
    RepositorioFormulario,
    RepositorioValidacion,
)
from infrastructure.configuracion import AppConfig
from infrastructure.dependencies import (
    obtener_config,
    obtener_extractor,
    obtener_repo_acceso,
    obtener_repo_auditoria,
    obtener_repo_documento,
    obtener_repo_expediente,
    obtener_repo_firma,
    obtener_repo_formulario,
    obtener_repo_validacion,
    obtener_storage,
)
from infrastructure.notificaciones.email_service import EmailService
from services.acceso_manual.acceso_manual_service import AccesoManualService
from services.auditoria.auditoria_service import AuditoriaService
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
    repo: RepositorioAccesoManual = Depends(obtener_repo_acceso),
    config: AppConfig = Depends(obtener_config),
) -> AccesoManualService:
    return AccesoManualService(repo, config.frontend_urls[0])


def obtener_servicio_email(
    config: AppConfig = Depends(obtener_config),
) -> INotificador:
    return EmailService(config.smtp)


def obtener_servicio_firma(
    request: Request,
    repo: RepositorioFirma = Depends(obtener_repo_firma),
    storage: IAlmacenamiento = Depends(obtener_storage),
    repo_auditoria: RepositorioAuditoria = Depends(obtener_repo_auditoria),
) -> FirmaService:
    config = request.app.state.config
    return FirmaService(
        repo=repo,
        zoho=request.app.state.zoho_sign,
        storage=storage,
        webhook_secret=config.zoho_sign.webhook_secret,
        repo_auditoria=repo_auditoria,
    )


def obtener_servicio_formulario(
    repo: RepositorioFormulario = Depends(obtener_repo_formulario),
    repo_doc: RepositorioDocumento = Depends(obtener_repo_documento),
    extractor: ExtractorIAImp = Depends(obtener_extractor),
    storage: IAlmacenamiento = Depends(obtener_storage),
    repo_auditoria: RepositorioAuditoria = Depends(obtener_repo_auditoria),
) -> FormularioService:
    return FormularioService(repo, repo_doc, extractor, storage, repo_auditoria)


def obtener_servicio_expediente(
    repo: RepositorioExpediente = Depends(obtener_repo_expediente),
    storage: IAlmacenamiento = Depends(obtener_storage),
    repo_auditoria: RepositorioAuditoria = Depends(obtener_repo_auditoria),
) -> ExpedienteService:
    return ExpedienteService(repo, storage, repo_auditoria)


def obtener_servicio_auditoria(
    request: Request,
    repo_auditoria: RepositorioAuditoria = Depends(obtener_repo_auditoria),
    repo_expediente: RepositorioExpediente = Depends(obtener_repo_expediente),
    config: AppConfig = Depends(obtener_config),
) -> AuditoriaService:
    return AuditoriaService(repo_auditoria, repo_expediente, config.secret_key)


def obtener_servicio_validacion(
    repo: RepositorioValidacion = Depends(obtener_repo_validacion),
    orquestador: OrquestadorValidacionDocumentos = Depends(obtener_orquestador),
    servicio_listas: ListaCautelaService = Depends(obtener_servicio_lista_cautela),
) -> ValidacionService:
    return ValidacionService(repo, orquestador, servicio_listas)
