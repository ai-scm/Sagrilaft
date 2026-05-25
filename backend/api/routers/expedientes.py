"""
Router de expedientes — portal interno SAGRILAFT.

Expone endpoints de solo lectura para consultar formularios enviados por
clientes y proveedores, incluyendo la descarga de documentos adjuntos.

SRP: parsea solicitudes HTTP y delega toda la lógica al ExpedienteService.
DIP: depende de api.dependencies, no de infrastructure directamente.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from api.dependencies import (
    obtener_servicio_acceso,
    obtener_servicio_email,
    obtener_servicio_expediente,
    obtener_servicio_firma,
)
from api.schemas import ExpedienteDetalle, ExpedienteResumen, ResumenDevolucion, SolicitudDevolucion
from services.acceso_manual.acceso_manual_service import AccesoManualService
from services.expedientes.expediente_service import ExpedienteService
from services.firma.firma_service import FirmaService

enrutador = APIRouter(prefix="/api/expedientes", tags=["expedientes"])


# ─── Listado ──────────────────────────────────────────────────────────────────

@enrutador.get(
    "/",
    response_model=List[ExpedienteResumen],
    summary="Listar formularios enviados",
    description=(
        "Devuelve todos los formularios en estado no-borrador (enviados, validados, rechazados), "
        "ordenados por fecha de actualización descendente. "
        "Acepta filtros opcionales por tipo de contraparte y búsqueda en razón social."
    ),
)
def listar_expedientes(
    tipo_contraparte: Optional[str] = Query(None, description="'CLIENTE' o 'PROVEEDOR'"),
    busqueda: Optional[str] = Query(None, description="Texto libre en razón social"),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> List[ExpedienteResumen]:
    return servicio.listar_expedientes(
        tipo_contraparte=tipo_contraparte,
        busqueda=busqueda,
    )


# ─── Detalle ──────────────────────────────────────────────────────────────────

@enrutador.get(
    "/{formulario_id}",
    response_model=ExpedienteDetalle,
    summary="Obtener detalle de expediente",
    description="Retorna los metadatos del expediente y sus documentos adjuntos. Los datos del formulario están disponibles exclusivamente en el PDF descargable.",
    responses={404: {"description": "Formulario no encontrado o en borrador"}},
)
def obtener_expediente(
    formulario_id: str,
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ExpedienteDetalle:
    return servicio.obtener_expediente(formulario_id)


# ─── Descarga de documentos ───────────────────────────────────────────────────

@enrutador.get(
    "/{formulario_id}/documentos/{doc_id}/descargar",
    summary="Descargar documento adjunto",
    description="Descarga un documento adjunto perteneciente a un expediente enviado.",
    responses={404: {"description": "Documento no encontrado o eliminado"}},
)
def descargar_documento(
    formulario_id: str,
    doc_id: str,
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> FileResponse:
    ruta, nombre_archivo, content_type = servicio.resolver_documento_para_descarga(
        formulario_id, doc_id
    )
    return FileResponse(
        path=ruta,
        filename=nombre_archivo,
        media_type=content_type,
    )


# ─── Aprobación / Rechazo ────────────────────────────────────────────────────

@enrutador.post(
    "/{formulario_id}/aprobar",
    summary="Aprobar formulario enviado",
    responses={400: {"description": "El formulario no está en estado 'enviado'"}},
)
def aprobar_expediente(
    formulario_id: str,
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    return servicio.aprobar_expediente(formulario_id)


@enrutador.post(
    "/{formulario_id}/rechazar",
    summary="Rechazar formulario",
    responses={400: {"description": "El formulario no puede rechazarse en su estado actual"}},
)
def rechazar_expediente(
    formulario_id: str,
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    return servicio.rechazar_expediente(formulario_id)


@enrutador.post(
    "/{formulario_id}/devolver",
    response_model=ResumenDevolucion,
    summary="Devolver formulario para corrección",
    description=(
        "Cambia el estado del formulario a 'en_correccion', registra las especificaciones "
        "de corrección y notifica al destinatario registrado por correo electrónico. "
        "Solo disponible en estados 'enviado' o 'validado'."
    ),
    responses={400: {"description": "El formulario no puede devolverse en su estado actual"}},
)
def devolver_expediente(
    formulario_id: str,
    solicitud: SolicitudDevolucion,
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
    acceso_service: AccesoManualService = Depends(obtener_servicio_acceso),
    email_service = Depends(obtener_servicio_email),
) -> ResumenDevolucion:
    return servicio.devolver_para_correccion(
        formulario_id=formulario_id,
        especificaciones=solicitud.especificaciones,
        campos_identificados=solicitud.campos_identificados,
        acceso_service=acceso_service,
        email_service=email_service,
    )


# ─── Firma electrónica ────────────────────────────────────────────────────────

@enrutador.post(
    "/{formulario_id}/enviar-a-firma",
    summary="Enviar formulario a firma electrónica",
    description=(
        "Envía el PDF del formulario a ZohoSign para firma electrónica. "
        "El formulario debe estar en estado 'validado'. "
        "ZohoSign notificará al firmante por correo electrónico."
    ),
    responses={
        400: {"description": "El formulario no está en estado 'validado'"},
        404: {"description": "Formulario no encontrado"},
    },
)
def enviar_a_firma(
    formulario_id: str,
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> dict:
    return servicio.enviar_a_firma(formulario_id)


@enrutador.post(
    "/{formulario_id}/verificar-firma",
    summary="Verificar estado de firma en ZohoSign",
    description="Consulta ZohoSign y actualiza el estado del formulario si la firma cambió. Alternativa al webhook para entornos sin URL pública.",
    responses={400: {"description": "Formulario no está en estado 'pendiente_firma'"}},
)
def verificar_estado_firma(
    formulario_id: str,
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> dict:
    return servicio.verificar_estado_firma(formulario_id)


@enrutador.post(
    "/{formulario_id}/cancelar-firma",
    summary="Cancelar solicitud de firma pendiente",
    description=(
        "Cancela la solicitud de firma en ZohoSign (recall) y devuelve el formulario "
        "al estado 'validado'. Solo disponible en estado 'pendiente_firma'."
    ),
    responses={
        400: {"description": "El formulario no está en estado 'pendiente_firma'"},
        404: {"description": "Formulario no encontrado"},
    },
)
def cancelar_firma(
    formulario_id: str,
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> dict:
    return servicio.cancelar_firma(formulario_id)


@enrutador.get(
    "/{formulario_id}/documento-firmado",
    summary="Descargar documento firmado",
    description="Descarga el PDF firmado electrónicamente. Solo disponible en estado 'firmado'.",
    responses={
        404: {"description": "Documento firmado no disponible"},
    },
)
def descargar_documento_firmado(
    formulario_id: str,
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> FileResponse:
    ruta = servicio.resolver_documento_firmado(formulario_id)
    es_zip = ruta.suffix == ".zip"
    return FileResponse(
        path=ruta,
        filename="formulario_firmado.zip" if es_zip else "formulario_firmado.pdf",
        media_type="application/zip" if es_zip else "application/pdf",
    )
