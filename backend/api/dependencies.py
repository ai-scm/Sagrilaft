"""
Dependencias FastAPI compartidas entre routers.

Centraliza los factories de servicios que necesitan Request + repositorios para
evitar duplicar la misma función en múltiples routers.
"""

from fastapi import Depends, Request

from core.configuracion import AppConfig
from infrastructure.dependencies import (
    obtener_config,
    obtener_repo_acceso,
    obtener_repo_firma,
)
from infrastructure.persistencia.repositorios import (
    RepositorioAccesoManualSQLAlchemy,
    RepositorioFirmaSQLAlchemy,
)
from services.acceso_manual.acceso_manual_service import AccesoManualService
from services.firma.firma_service import FirmaService
from infrastructure.notificaciones.email_service import EmailService


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


def obtener_servicio_acceso(
    repo: RepositorioAccesoManualSQLAlchemy = Depends(obtener_repo_acceso),
    config: AppConfig = Depends(obtener_config),
) -> AccesoManualService:
    return AccesoManualService(repo, config.frontend_urls[0])


def obtener_servicio_email(
    config: AppConfig = Depends(obtener_config),
) -> EmailService:
    return EmailService(config.smtp)
