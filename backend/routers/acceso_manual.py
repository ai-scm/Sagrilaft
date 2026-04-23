"""
Router de accesos manuales — portal interno SAGRILAFT.

Expone endpoints para que equipos de Ventas, Legal y Finanzas generen
y consulten accesos manuales al formulario SAGRILAFT.

SRP: parsea solicitudes HTTP y delega toda la lógica al AccesoManualService.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.configuracion import AppConfig
from database import get_db
from dependencies import obtener_config
from schemas import (
    AccesoManualCreado,
    AccesoManualResumen,
    FormularioConDetalles,
    SolicitudAccesoManual,
)
from services.acceso_manual.acceso_manual_service import AccesoManualService

enrutador = APIRouter(prefix="/api/accesos-manuales", tags=["accesos-manuales"])


def _obtener_servicio(
    sesion: Session = Depends(get_db),
    config: AppConfig = Depends(obtener_config),
) -> AccesoManualService:
    """
    Construye el AccesoManualService usando FRONTEND_URL de la configuración,
    que apunta a la aplicación React (no al backend FastAPI).
    """
    return AccesoManualService(sesion, config.frontend_urls[0])


# ─── Creación ────────────────────────────────────────────────────────────────

@enrutador.post(
    "/",
    response_model=AccesoManualCreado,
    status_code=201,
    summary="Crear acceso manual",
    description=(
        "Genera credenciales únicas (código de petición + PIN) para que un cliente "
        "o proveedor acceda al formulario SAGRILAFT. El PIN se devuelve UNA SOLA VEZ "
        "y nunca se vuelve a exponer desde el backend."
    ),
)
def crear_acceso_manual(
    solicitud_acceso: SolicitudAccesoManual,
    servicio: AccesoManualService = Depends(_obtener_servicio),
) -> AccesoManualCreado:
    return servicio.crear_acceso(solicitud_acceso)


# ─── Listado ─────────────────────────────────────────────────────────────────

@enrutador.get(
    "/",
    response_model=List[AccesoManualResumen],
    summary="Listar accesos manuales",
    description="Devuelve todos los accesos creados con su estado de formulario asociado.",
)
def listar_accesos_manuales(
    servicio: AccesoManualService = Depends(_obtener_servicio),
) -> List[AccesoManualResumen]:
    return servicio.listar_accesos()


# ─── Resolución de token ──────────────────────────────────────────────────────

@enrutador.get(
    "/token/{token}",
    response_model=FormularioConDetalles,
    summary="Resolver token de diligenciamiento",
    description=(
        "Valida el token incluido en el enlace enviado al destinatario y devuelve "
        "el formulario SAGRILAFT pre-inicializado. El destinatario externo usa este "
        "endpoint al hacer clic en el enlace recibido por correo."
    ),
    responses={
        404: {"description": "Token inválido, no encontrado o ya consumido"},
        410: {"description": "El enlace de diligenciamiento ha expirado"},
    },
)
def resolver_token_diligenciamiento(
    token: str,
    servicio: AccesoManualService = Depends(_obtener_servicio),
) -> FormularioConDetalles:
    return servicio.resolver_token(token)
