"""
Router de auditoría y trazabilidad — portal interno SAGRILAFT.

Expone:
  GET  /api/auditoria/dashboard           — métricas operativas en tiempo real
  GET  /api/auditoria/{id}/eventos        — línea de tiempo de eventos de un expediente
  GET  /api/auditoria/{id}/reporte-pdf    — reporte PDF de cadena de custodia
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.dependencies import obtener_servicio_auditoria
from api.middleware.autenticacion import UsuarioPortalInterno, portal_interno
from services.auditoria.auditoria_service import AuditoriaService

enrutador = APIRouter(
    prefix="/api/auditoria",
    tags=["auditoria"],
)


@enrutador.get(
    "/dashboard",
    summary="Métricas operativas de expedientes",
    description=(
        "Devuelve conteo de expedientes por estado, formularios estancados (sin movimiento "
        f"en más de 5 días) y tiempo promedio de permanencia por estado."
    ),
)
def dashboard_metricas(
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: AuditoriaService = Depends(obtener_servicio_auditoria),
) -> dict:
    return servicio.metricas_dashboard()


@enrutador.get(
    "/{formulario_id}/eventos",
    summary="Línea de tiempo de eventos de un expediente",
    description=(
        "Devuelve todos los eventos del ciclo de vida del formulario en orden cronológico: "
        "aprobaciones, rechazos, devoluciones, eventos de firma y alertas de cambio directo en BD."
    ),
    responses={404: {"description": "Formulario no encontrado"}},
)
def listar_eventos_expediente(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: AuditoriaService = Depends(obtener_servicio_auditoria),
) -> list:
    return servicio.obtener_eventos(formulario_id)


@enrutador.get(
    "/{formulario_id}/reporte-pdf",
    summary="Reporte PDF de auditoría (cadena de custodia)",
    description=(
        "Genera y descarga un PDF con la línea de tiempo completa de eventos, "
        "documentos con hash SHA-256 y firma HMAC del reporte para verificación de integridad. "
        "Solo disponible para formularios en estado no-borrador."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF de auditoría"},
        404: {"description": "Formulario no encontrado o en borrador"},
        500: {"description": "WeasyPrint no disponible"},
    },
)
def reporte_pdf_auditoria(
    formulario_id: str,
    usuario: UsuarioPortalInterno = Depends(portal_interno),
    servicio: AuditoriaService = Depends(obtener_servicio_auditoria),
) -> Response:
    pdf_bytes = servicio.generar_reporte_pdf(formulario_id)
    nombre = f"auditoria_{formulario_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
