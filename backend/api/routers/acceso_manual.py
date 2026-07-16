"""
Router de accesos manuales — portal interno SAGRILAFT.

Expone endpoints para que equipos de Ventas, Legal y Finanzas generen
y consulten accesos manuales al formulario SAGRILAFT.

SRP: parsea solicitudes HTTP y delega toda la lógica al AccesoManualService.
"""

from typing import List

from fastapi import APIRouter, Depends, Request

from api.dependencies import obtener_servicio_acceso
from api.limitador import limitador
from api.middleware.autenticacion import portal_interno
from api.schemas import (
    AccesoManualCreado,
    AccesoManualResumen,
    ActualizarCorreoAcceso,
    EstadoCorreoAcceso,
    FormularioConDetalles,
    SolicitudAccesoManual,
)
from domain.contratos import SolicitudCreacionAcceso
from services.acceso_manual.acceso_manual_service import AccesoManualService

enrutador = APIRouter(prefix="/api/accesos-manuales", tags=["accesos-manuales"])


# ─── 1. Creación ──────────────────────────────────────────────────────────────

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
    dependencies=[Depends(portal_interno)],
)
def crear_acceso_manual_contraparte(
    solicitud_acceso_manual: SolicitudAccesoManual,
    servicio_acceso_manual: AccesoManualService = Depends(obtener_servicio_acceso),
) -> AccesoManualCreado:
    solicitud_dominio = SolicitudCreacionAcceso(
        tipo_contraparte=solicitud_acceso_manual.tipo_contraparte.value,
        razon_social=solicitud_acceso_manual.razon_social,
        correo_destinatario=str(solicitud_acceso_manual.correo_destinatario) if solicitud_acceso_manual.correo_destinatario else None,
        area_responsable=solicitud_acceso_manual.area_responsable.value,
    )
    return servicio_acceso_manual.crear_acceso(solicitud_dominio)

@enrutador.post(
    "/{acceso_id}/reenviar",
    response_model=AccesoManualCreado,
    status_code=200,
    summary="Reenviar acceso manual",
    description="Regenera el PIN y reenvía el correo de acceso manual.",
    dependencies=[Depends(portal_interno)],
)
def reenviar_acceso_manual_contraparte(
    acceso_id: str,
    servicio_acceso_manual: AccesoManualService = Depends(obtener_servicio_acceso),
) -> AccesoManualCreado:
    return servicio_acceso_manual.reenviar_acceso(acceso_id)


# ─── 2. Listado ───────────────────────────────────────────────────────────────

@enrutador.get(
    "/",
    response_model=List[AccesoManualResumen],
    summary="Listar accesos manuales",
    description="Devuelve todos los accesos creados ordenados del más reciente al más antiguo, con su estado calculado (activo, consumido o expirado).",
    dependencies=[Depends(portal_interno)],
)
def obtener_accesos_manuales_creados(
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> List[AccesoManualResumen]:
    return servicio.listar_accesos()


# ─── 3. Gestión de correo del destinatario ────────────────────────────────────

@enrutador.get(
    "/token/{token}/estado-correo",
    response_model=EstadoCorreoAcceso,
    summary="Verificar si el acceso tiene correo registrado",
    description=(
        "Endpoint liviano para comprobar si el destinatario ya registró su correo. "
        "No devuelve datos del formulario. Usado por el frontend al cargar la página "
        "para decidir si debe mostrar el modal de captura de correo."
    ),
    responses={
        404: {"description": "Token inválido o no encontrado"},
        410: {"description": "El acceso ha expirado"},
        429: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit("60/minute")
def consultar_estado_correo_acceso(
    request: Request,
    token: str,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> EstadoCorreoAcceso:
    correo_registrado = servicio.verificar_estado_correo(token)
    return EstadoCorreoAcceso(correo_registrado=correo_registrado)


@enrutador.patch(
    "/token/{token}/correo",
    status_code=204,
    summary="Registrar correo del destinatario",
    description="Permite al destinatario externo registrar su correo electrónico antes de iniciar el diligenciamiento.",
    responses={
        404: {"description": "Token inválido, no encontrado o ya consumido"},
        410: {"description": "El acceso ha expirado"},
        429: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit("10/minute")
def capturar_correo_desde_acceso_manual(
    request: Request,
    token: str,
    payload: ActualizarCorreoAcceso,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> None:
    servicio.registrar_correo_desde_token(token, payload.correo_destinatario)


# ─── 4. Resolución de token y diligenciamiento ─────────────────────────────────

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
        429: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit("30/minute")
def obtener_formulario_por_codigo_acceso(
    request: Request,
    token: str,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> FormularioConDetalles:
    return servicio.resolver_token(token)
