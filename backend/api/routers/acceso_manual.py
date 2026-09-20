"""
Router de accesos manuales — portal interno SAGRILAFT.

Expone endpoints para que equipos de Ventas, Legal y Finanzas generen
y consulten accesos manuales al formulario SAGRILAFT.

SRP: parsea solicitudes HTTP y delega toda la lógica al AccesoManualService.
"""

from typing import List

from fastapi import APIRouter, Depends, Request, status

from api.dependencies import obtener_servicio_acceso
from api.limitador import limitador
from api.middleware.autenticacion import UsuarioPortalInterno, portal_interno
from api.rbac import contrapartes_permitidas
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

_RATE_LIMIT_CONSULTA_CORREO = "60/minute"
_RATE_LIMIT_REGISTRO_CORREO = "10/minute"
_RATE_LIMIT_RESOLUCION_TOKEN = "30/minute"


# ─── 1. Creación ──────────────────────────────────────────────────────────────

@enrutador.post(
    "/",
    response_model=AccesoManualCreado,
    status_code=status.HTTP_201_CREATED,
    summary="Crear acceso manual",
    description=(
        "Genera credenciales únicas (código de petición + PIN) para que un cliente "
        "o proveedor acceda al formulario SAGRILAFT. El PIN se devuelve UNA SOLA VEZ "
        "y nunca se vuelve a exponer desde el backend."
    ),
)
def crear_acceso_manual_contraparte(
    solicitud_acceso_manual: SolicitudAccesoManual,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio_acceso_manual: AccesoManualService = Depends(obtener_servicio_acceso),
) -> AccesoManualCreado:
    solicitud_dominio = SolicitudCreacionAcceso(
        tipo_contraparte=solicitud_acceso_manual.tipo_contraparte.value,
        razon_social=solicitud_acceso_manual.razon_social,
        correo_destinatario=str(solicitud_acceso_manual.correo_destinatario),
        area_responsable=solicitud_acceso_manual.area_responsable.value,
    )
    return servicio_acceso_manual.crear_acceso(
        solicitud_dominio,
        contrapartes_permitidas(usuario),
    )

@enrutador.post(
    "/{acceso_id}/reenviar",
    response_model=AccesoManualCreado,
    status_code=status.HTTP_200_OK,
    summary="Reenviar acceso manual",
    description="Regenera el PIN y reenvía el correo de acceso manual.",
)
def reenviar_acceso_manual_contraparte(
    acceso_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio_acceso_manual: AccesoManualService = Depends(obtener_servicio_acceso),
) -> AccesoManualCreado:
    return servicio_acceso_manual.reenviar_acceso(
        acceso_id,
        contrapartes_permitidas(usuario),
    )


# ─── 2. Listado ───────────────────────────────────────────────────────────────

@enrutador.get(
    "/",
    response_model=List[AccesoManualResumen],
    summary="Listar accesos manuales",
    description="Devuelve todos los accesos creados ordenados del más reciente al más antiguo, con su estado calculado (activo, consumido o expirado).",
)
def obtener_accesos_manuales_creados(
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> List[AccesoManualResumen]:
    return servicio.listar_accesos(contrapartes_permitidas(usuario))


# ─── 3. Gestión de correo del destinatario ────────────────────────────────────

@enrutador.get(
    "/token/{token}/estado-correo",
    response_model=EstadoCorreoAcceso,
    summary="Verificar si el acceso tiene correo registrado",
    description=(
        "Endpoint liviano de compatibilidad para comprobar si un acceso historico "
        "tiene correo registrado. En el flujo principal actual el correo es "
        "obligatorio al crear el acceso manual. No devuelve datos del formulario."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Token inválido o no encontrado"},
        status.HTTP_410_GONE: {"description": "El acceso ha expirado"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit(_RATE_LIMIT_CONSULTA_CORREO)
def consultar_estado_correo_acceso(
    request: Request,
    token: str,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> EstadoCorreoAcceso:
    correo_registrado = servicio.verificar_estado_correo(token)
    return EstadoCorreoAcceso(correo_registrado=correo_registrado)


@enrutador.patch(
    "/token/{token}/correo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Registrar correo del destinatario",
    description=(
        "Endpoint de compatibilidad para registrar correo en accesos historicos. "
        "En el flujo principal actual el correo es obligatorio al crear el acceso."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Token inválido, no encontrado o ya consumido"},
        status.HTTP_410_GONE: {"description": "El acceso ha expirado"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit(_RATE_LIMIT_REGISTRO_CORREO)
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
        status.HTTP_404_NOT_FOUND: {"description": "Token inválido, no encontrado o ya consumido"},
        status.HTTP_410_GONE: {"description": "El acceso ha expirado"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Demasiadas solicitudes. Espere un momento antes de reintentar"},
    },
)
@limitador.limit(_RATE_LIMIT_RESOLUCION_TOKEN)
def obtener_formulario_por_codigo_acceso(
    request: Request,
    token: str,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> FormularioConDetalles:
    return servicio.resolver_token(token)
