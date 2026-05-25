"""
Router de accesos manuales — portal interno SAGRILAFT.

Expone endpoints para que equipos de Ventas, Legal y Finanzas generen
y consulten accesos manuales al formulario SAGRILAFT.

SRP: parsea solicitudes HTTP y delega toda la lógica al AccesoManualService.
"""

from typing import List

from fastapi import APIRouter, Depends

from api.dependencies import obtener_servicio_acceso
from api.schemas import (
    AccesoManualCreado,
    AccesoManualResumen,
    FormularioConDetalles,
    SolicitudAccesoManual,
)
from domain.contratos import SolicitudCreacionAcceso
from services.acceso_manual.acceso_manual_service import AccesoManualService

enrutador = APIRouter(prefix="/api/accesos-manuales", tags=["accesos-manuales"])


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
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> AccesoManualCreado:
    solicitud_dominio = SolicitudCreacionAcceso(
        tipo_contraparte=solicitud_acceso.tipo_contraparte.value,
        razon_social=solicitud_acceso.razon_social,
        correo_destinatario=str(solicitud_acceso.correo_destinatario),
        area_responsable=solicitud_acceso.area_responsable.value,
    )
    return servicio.crear_acceso(solicitud_dominio)


# ─── Listado ─────────────────────────────────────────────────────────────────

@enrutador.get(
    "/",
    response_model=List[AccesoManualResumen],
    summary="Listar accesos manuales",
    description="Devuelve todos los accesos creados ordenados del más reciente al más antiguo, con su estado calculado (activo, consumido o expirado).",
)
def listar_accesos_manuales(
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
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
        410: {"description": "El acceso ha expirado"},
    },
)
def resolver_token_diligenciamiento(
    token: str,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> FormularioConDetalles:
    return servicio.resolver_token(token)
