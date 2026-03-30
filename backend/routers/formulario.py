"""
Router de formularios — responsabilidades HTTP exclusivamente.

SRP : parsea solicitudes, delega al servicio y devuelve respuestas.
      Toda la lógica de negocio vive en FormularioService.
DIP : depende de la abstracción IExtractorIA, no de la implementación Bedrock.
"""

from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from dependencies import obtener_extractor
from schemas import (
    DocumentoResponse,
    FormularioConDetalles,
    FormularioCreate,
    FormularioResponse,
    FormularioUpdate,
    ResultadoValidacionEnvio,
)
from core.contracts import IExtractorIA
from services.formulario.formulario_service import FormularioService
from routers.transformers import construir_respuesta_documento

enrutador = APIRouter(prefix="/api/formularios", tags=["formularios"])


# ─── Fábrica de dependencias ─────────────────────────────────────────────────

def obtener_servicio_formulario(
    sesion: Session = Depends(get_db),
    extractor: IExtractorIA = Depends(obtener_extractor),
) -> FormularioService:
    """Crea un FormularioService con las dependencias inyectadas."""
    return FormularioService(sesion, extractor)


# ─── Endpoints de formulario ─────────────────────────────────────────────────

@enrutador.post("/", response_model=FormularioResponse)
def crear_formulario(
    datos: FormularioCreate,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> FormularioResponse:
    """Crea un nuevo formulario en estado borrador."""
    return servicio.crear_borrador(datos)


@enrutador.get("/{formulario_id}", response_model=FormularioConDetalles)
def obtener_formulario(
    formulario_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> FormularioConDetalles:
    """Obtiene un formulario por código de petición o identificador único."""
    return servicio.obtener_por_codigo(formulario_id)


@enrutador.put("/{formulario_id}", response_model=FormularioResponse)
def actualizar_formulario(
    formulario_id: str,
    datos: FormularioUpdate,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> FormularioResponse:
    """Actualiza un formulario en estado borrador (guardado parcial)."""
    return servicio.actualizar(formulario_id, datos)


@enrutador.post("/{formulario_id}/enviar", response_model=ResultadoValidacionEnvio)
def enviar_formulario(
    formulario_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> ResultadoValidacionEnvio:
    """Envío final del formulario. Valida campos requeridos y bloquea edición posterior."""
    return servicio.enviar(formulario_id)


# ─── Endpoints de documentos adjuntos ────────────────────────────────────────

@enrutador.post("/{formulario_id}/documentos", response_model=DocumentoResponse)
async def subir_documento(
    formulario_id: str,
    tipo_documento: str = Form(...),
    archivo: UploadFile = File(...),
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> DocumentoResponse:
    """
    Sube un documento y extrae sus datos con IA de forma inmediata.

    Flujo event-driven: cada carga dispara UNA sola llamada a Bedrock
    para el tipo_documento recibido, sin iterar sobre otros documentos.
    """
    contenido = await archivo.read()
    resultado = await servicio.guardar_documento(
        formulario_id=formulario_id,
        tipo_documento=tipo_documento,
        contenido_bytes=contenido,
        nombre_archivo=archivo.filename,
        content_type=archivo.content_type,
    )
    return construir_respuesta_documento(resultado)


@enrutador.delete("/{formulario_id}/documentos/{doc_id}")
def eliminar_documento(
    formulario_id: str,
    doc_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> dict:
    """Elimina un documento adjunto del formulario."""
    servicio.eliminar_documento(formulario_id, doc_id)
    return {"mensaje": "Documento eliminado"}


@enrutador.get("/{formulario_id}/documentos", response_model=List[DocumentoResponse])
def listar_documentos(
    formulario_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> List[DocumentoResponse]:
    """Lista todos los documentos adjuntos de un formulario."""
    return servicio.listar_documentos(formulario_id)


# ─── Endpoints de pre-llenado con IA ─────────────────────────────────────────

@enrutador.post("/{formulario_id}/documentos/{doc_id}/prefill")
async def prellenar_desde_documento(
    formulario_id: str,
    doc_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> dict:
    """
    Escanea un documento con IA y retorna campos sugeridos para pre-llenado.

    El sistema procesa el adjunto y sugiere valores para el formulario
    con base en la información extraída.
    """
    return await servicio.prellenar_documento(formulario_id, doc_id)


@enrutador.post("/{formulario_id}/prefill-all")
async def prellenar_todos_documentos(
    formulario_id: str,
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> dict:
    """
    Escanea todos los documentos adjuntos con IA y retorna campos
    consolidados para pre-llenado completo del formulario.
    """
    return await servicio.prellenar_todos(formulario_id)
