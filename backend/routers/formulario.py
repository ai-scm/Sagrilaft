"""
Router de formularios — solo responsabilidades HTTP.

SRP: este módulo únicamente parsea requests, delega al servicio y
devuelve responses. Toda la lógica de negocio vive en FormularioService.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from dependencies import get_extractor
from schemas import (
    FormularioCreate, FormularioUpdate, FormularioResponse,
    FormularioConDetalles, DocumentoResponse,
    ResultadoValidacionEnvio,
)
from services.contracts import IAIExtractor
from services.formulario_service import FormularioService

router = APIRouter(prefix="/api/formularios", tags=["formularios"])


def get_formulario_service(
    db: Session = Depends(get_db),
    extractor: IAIExtractor = Depends(get_extractor),
) -> FormularioService:
    """Factory de FormularioService con dependencias inyectadas."""
    return FormularioService(db, extractor)


# === ENDPOINTS ===

@router.post("/", response_model=FormularioResponse)
def crear_formulario(
    data: FormularioCreate,
    service: FormularioService = Depends(get_formulario_service),
):
    """Crear un nuevo formulario (comienza como borrador)."""
    return service.crear_borrador(data)


@router.get("/{codigo}", response_model=FormularioConDetalles)
def obtener_formulario(
    codigo: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """Obtener formulario por código de petición o ID."""
    return service.obtener_por_codigo(codigo)


@router.put("/{id}", response_model=FormularioResponse)
def actualizar_formulario(
    id: str,
    data: FormularioUpdate,
    service: FormularioService = Depends(get_formulario_service),
):
    """Actualizar formulario (guardado parcial). Solo si está en borrador."""
    return service.actualizar(id, data)


@router.post("/{id}/enviar", response_model=ResultadoValidacionEnvio)
def enviar_formulario(
    id: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """Envío final del formulario. Valida campos requeridos y bloquea edición."""
    return service.enviar(id)


@router.post("/{id}/documentos", response_model=DocumentoResponse)
async def subir_documento(
    id: str,
    tipo_documento: str = Form(...),
    archivo: UploadFile = File(...),
    service: FormularioService = Depends(get_formulario_service),
):
    """
    Sube un documento y extrae sus datos con IA de forma inmediata.

    Flujo event-driven: cada upload dispara UNA sola llamada a Bedrock
    para el tipo_documento recibido. No itera sobre otros documentos.
    """
    content = await archivo.read()
    documento, campos_sugeridos = await service.guardar_documento(
        formulario_id=id,
        tipo_documento=tipo_documento,
        contenido_bytes=content,
        nombre_archivo=archivo.filename,
        content_type=archivo.content_type,
    )

    return DocumentoResponse(
        id=documento.id,
        tipo_documento=documento.tipo_documento,
        nombre_archivo=documento.nombre_archivo,
        content_type=documento.content_type,
        tamano=documento.tamano,
        created_at=documento.created_at,
        campos_sugeridos=campos_sugeridos if campos_sugeridos else None,
    )


@router.delete("/{id}/documentos/{doc_id}")
def eliminar_documento(
    id: str,
    doc_id: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """Eliminar un documento adjunto."""
    service.eliminar_documento(id, doc_id)
    return {"message": "Documento eliminado"}


@router.get("/{id}/documentos", response_model=List[DocumentoResponse])
def listar_documentos(
    id: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """Listar documentos adjuntos de un formulario."""
    return service.listar_documentos(id)


@router.post("/{id}/documentos/{doc_id}/prefill")
async def prefill_desde_documento(
    id: str,
    doc_id: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """
    Escanea un documento con IA y retorna campos sugeridos para pre-llenar.

    Tarea 4 del README: el sistema procesa los adjuntos y sugiere
    valores para el formulario con base en la información extraída.
    """
    return await service.prefill_documento(id, doc_id)


@router.post("/{id}/prefill-all")
async def prefill_todos_documentos(
    id: str,
    service: FormularioService = Depends(get_formulario_service),
):
    """
    Escanea TODOS los documentos adjuntos y retorna campos consolidados
    para pre-llenar el formulario completo.
    """
    return await service.prefill_todos(id)
