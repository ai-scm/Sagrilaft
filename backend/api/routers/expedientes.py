"""
Router de expedientes — portal interno SAGRILAFT.

Expone endpoints de solo lectura para consultar formularios enviados por
clientes y proveedores, incluyendo la descarga de documentos adjuntos.

SRP: parsea solicitudes HTTP y delega toda la lógica al ExpedienteService.
DIP: depende de api.dependencies, no de infrastructure directamente.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, RedirectResponse
from starlette.responses import Response

from api.dependencies import (
    obtener_servicio_expediente,
    obtener_servicio_firma,
)
from api.middleware.autenticacion import UsuarioPortalInterno, portal_interno
from domain.excepciones import SinPermisoError
from domain.constantes import CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS
from api.schemas import (
    ComparacionVersionFormulario,
    ExpedienteDetalle,
    ExpedienteResumen,
    ResumenCierreExpediente,
    ResumenDevolucion,
    ResumenReaperturaActualizacion,
    ResumenRechazo,
    SolicitudDevolucion,
    SolicitudReaperturaActualizacion,
    SolicitudRechazo,
)
from services.expedientes.expediente_service import ExpedienteService
from services.firma.firma_service import FirmaService

enrutador = APIRouter(
    prefix="/api/expedientes",
    tags=["expedientes"],
)

_ROLES_A_CONTRAPARTES = {
    "acceso_clientes": "cliente",
    "acceso_proveedores": "proveedor",
}

def _contrapartes_permitidas(usuario: UsuarioPortalInterno) -> list[str]:
    """Deriva las carpetas visibles según los roles del operador autenticado."""

    permitidas = [
        tipo
        for rol, tipo in _ROLES_A_CONTRAPARTES.items()
        if usuario.tiene_rol(rol)
    ]

    if not permitidas:
        raise SinPermisoError("sin_roles")

    return permitidas

# ─── 1. Listado y consulta ─────────────────────────────────────────────────────

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
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> List[ExpedienteResumen]:
    return servicio.listar_expedientes(
        tipo_contraparte=tipo_contraparte,
        busqueda=busqueda,
        contrapartes_permitidas=_contrapartes_permitidas(usuario),
    )


@enrutador.get(
    "/{formulario_id}",
    response_model=ExpedienteDetalle,
    summary="Obtener detalle de expediente",
    description="Retorna los metadatos del expediente y sus documentos adjuntos. Los datos del formulario están disponibles exclusivamente en el PDF descargable.",
    responses={404: {"description": "Formulario no encontrado o en borrador"}},
)
def obtener_expediente(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ExpedienteDetalle:
    return servicio.obtener_expediente(formulario_id, _contrapartes_permitidas(usuario))


@enrutador.get(
    "/{formulario_id}/comparacion-versiones",
    response_model=ComparacionVersionFormulario,
    summary="Comparar última versión corregida",
    description="Compara la última versión del PDF del formulario contra su versión anterior inmediata.",
)
def comparar_ultima_correccion(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ComparacionVersionFormulario:
    return servicio.comparar_ultima_correccion(formulario_id, _contrapartes_permitidas(usuario))


@enrutador.get(
    "/{formulario_id}/comparacion-versiones/reporte-pdf",
    summary="Descargar evidencia de cambios",
    description="Genera un PDF con la comparación estructurada entre la última versión y la anterior.",
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF de evidencia"}},
)
def descargar_reporte_comparacion(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> Response:
    pdf_bytes = servicio.generar_reporte_comparacion_pdf(
        formulario_id,
        _contrapartes_permitidas(usuario),
    )
    headers = {
        "Content-Disposition": f'attachment; filename="comparacion_{formulario_id[:8]}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@enrutador.get(
    "/{formulario_id}/documentos/{doc_id}/descargar",
    summary="Descargar documento adjunto",
    description="Descarga un documento adjunto perteneciente a un expediente enviado.",
    responses={404: {"description": "Documento no encontrado o eliminado"}},
)
def descargar_documento(
    formulario_id: str,
    doc_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> Response:
    info = servicio.resolver_documento_para_descarga(formulario_id, doc_id, _contrapartes_permitidas(usuario))
    if info.es_url:
        return RedirectResponse(url=info.valor, status_code=307)
    return FileResponse(path=info.valor, filename=info.nombre_archivo, media_type=info.content_type)


# ─── 2. Carga y actualización de documentos ────────────────────────────────────

@enrutador.post(
    "/{formulario_id}/carga-manual",
    summary="Cargar formulario manualmente",
    description="Permite a un operador subir un PDF y reemplazar la versión actual, reanudando el flujo de revisión.",
)
async def carga_manual_expediente(
    formulario_id: str,
    justificacion: str = Form(...),
    archivo: UploadFile = File(...),
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    if archivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Solo se permite subir archivos PDF.")
    if len(justificacion.strip()) < 20:
        raise HTTPException(status_code=400, detail="La justificación debe tener al menos 20 caracteres.")
        
    contenido = await archivo.read()
    try:
        return servicio.cargar_formulario_manual(
            formulario_id=formulario_id,
            archivo_bytes=contenido,
            nombre_archivo=archivo.filename,
            content_type=archivo.content_type,
            justificacion=justificacion,
            actor_id=usuario.email,
            contrapartes_permitidas=_contrapartes_permitidas(usuario),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@enrutador.post(
    "/{formulario_id}/reporte-final",
    response_model=ResumenCierreExpediente,
    summary="Cerrar expediente",
    description=(
        "Cierra el expediente con causal de cierre. El informe final PDF es obligatorio, "
        "excepto cuando la causal es no_continuacion_dialogos."
    ),
)
async def carga_reporte_final(
    formulario_id: str,
    causal_cierre: str = Form(...),
    justificacion: Optional[str] = Form(""),
    archivo: Optional[UploadFile] = File(None),
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ResumenCierreExpediente:
    if archivo is None:
        if causal_cierre != CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS:
            raise HTTPException(status_code=400, detail="El informe final en PDF es obligatorio para esta causal de cierre.")
        try:
            return servicio.cerrar_sin_reporte_final(
                formulario_id=formulario_id,
                justificacion=justificacion or "",
                actor_id=usuario.email,
                causal_cierre=causal_cierre,
                contrapartes_permitidas=_contrapartes_permitidas(usuario),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if archivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Solo se permite subir archivos PDF para el reporte final.")
        
    contenido = await archivo.read()
    try:
        return servicio.cargar_reporte_final(
            formulario_id=formulario_id,
            archivo_bytes=contenido,
            nombre_archivo=archivo.filename,
            content_type=archivo.content_type,
            justificacion=justificacion,
            actor_id=usuario.email,
            causal_cierre=causal_cierre,
            contrapartes_permitidas=_contrapartes_permitidas(usuario),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@enrutador.post(
    "/{formulario_id}/reabrir-actualizacion",
    response_model=ResumenReaperturaActualizacion,
    summary="Reabrir expediente por actualización",
    description=(
        "Reabre una carpeta cerrada de tipo actualización para continuar el ciclo periódico. "
        "Conserva documentos e informe final existentes."
    ),
)
def reabrir_actualizacion(
    formulario_id: str,
    solicitud: SolicitudReaperturaActualizacion,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ResumenReaperturaActualizacion:
    return servicio.reabrir_por_actualizacion(
        formulario_id=formulario_id,
        justificacion=solicitud.justificacion,
        actor_id=usuario.email,
        contrapartes_permitidas=_contrapartes_permitidas(usuario),
    )


# ─── 3. Transiciones de estado (Aprobar, Rechazar, Devolver) ──────────────────

@enrutador.post(
    "/{formulario_id}/aprobar",
    summary="Aprobar formulario enviado",
    responses={400: {"description": "El formulario no está en estado 'enviado'"}},
)
def aprobar_expediente(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    return servicio.aprobar_expediente(
        formulario_id,
        _contrapartes_permitidas(usuario),
        actor_id=usuario.email,
    )


@enrutador.post(
    "/{formulario_id}/rechazar",
    response_model=ResumenRechazo,
    summary="Rechazar formulario",
    description=(
        "Rechaza el formulario de forma definitiva registrando el motivo en auditoría. "
        "Si el operador redacta un mensaje_para_destinatario, se envía una notificación "
        "por correo al destinatario sin exponer el motivo interno. "
        "Solo disponible en estados 'enviado' o 'validado'."
    ),
    responses={400: {"description": "El formulario no puede rechazarse en su estado actual"}},
)
def rechazar_expediente(
    formulario_id: str,
    solicitud: SolicitudRechazo,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ResumenRechazo:
    return servicio.rechazar_expediente(
        formulario_id,
        _contrapartes_permitidas(usuario),
        actor_id=usuario.email,
        motivo=solicitud.motivo,
        mensaje_para_destinatario=solicitud.mensaje_para_destinatario,
    )


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
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: ExpedienteService = Depends(obtener_servicio_expediente),
) -> ResumenDevolucion:
    return servicio.devolver_para_correccion(
        formulario_id=formulario_id,
        especificaciones=solicitud.especificaciones,
        campos_identificados=solicitud.campos_identificados,
        contrapartes_permitidas=_contrapartes_permitidas(usuario),
        actor_id=usuario.email,
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
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: FirmaService = Depends(obtener_servicio_firma),
    servicio_exp: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    servicio_exp.obtener_expediente(formulario_id, _contrapartes_permitidas(usuario))
    return servicio.enviar_a_firma(formulario_id, actor_id=usuario.email)


@enrutador.post(
    "/{formulario_id}/verificar-firma",
    summary="Verificar estado de firma en ZohoSign",
    description="Consulta ZohoSign y actualiza el estado del formulario si la firma cambió. Alternativa al webhook para entornos sin URL pública.",
    responses={400: {"description": "Formulario no está en estado 'pendiente_firma'"}},
)
def verificar_estado_firma(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: FirmaService = Depends(obtener_servicio_firma),
    servicio_exp: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    servicio_exp.obtener_expediente(formulario_id, _contrapartes_permitidas(usuario))
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
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: FirmaService = Depends(obtener_servicio_firma),
    servicio_exp: ExpedienteService = Depends(obtener_servicio_expediente),
) -> dict:
    servicio_exp.obtener_expediente(formulario_id, _contrapartes_permitidas(usuario))
    return servicio.cancelar_firma(formulario_id, actor_id=usuario.email)


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
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: FirmaService = Depends(obtener_servicio_firma),
    servicio_exp: ExpedienteService = Depends(obtener_servicio_expediente),
) -> Response:
    servicio_exp.obtener_expediente(formulario_id, _contrapartes_permitidas(usuario))
    info = servicio.resolver_documento_firmado(formulario_id)
    if info.es_url:
        return RedirectResponse(url=info.valor, status_code=307)
    return FileResponse(path=info.valor, filename=info.nombre_archivo, media_type=info.content_type)
