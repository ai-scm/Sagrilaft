"""
Router de validación de formularios.

Responsabilidad exclusiva: recibir la solicitud HTTP, delegar al ValidacionService
y traducir excepciones de dominio a respuestas HTTP apropiadas.

SRP : sin lógica de negocio ni orquestación — esa vive en ValidacionService.
DIP : depende de api.dependencies, no de infrastructure directamente.
"""

from typing import List

from fastapi import APIRouter, Depends

from api.dependencies import obtener_servicio_validacion
from api.schemas import ValidacionResponse
from domain.validacion.resultado import ResultadoValidacionDominio
from services.validacion.validacion_service import ValidacionService

enrutador = APIRouter(prefix="/api/validar", tags=["validación"])


# ─── Endpoint ────────────────────────────────────────────────────────────────

@enrutador.post("/{formulario_id}", response_model=List[ValidacionResponse])
async def validar_formulario(
    formulario_id: str,
    servicio: ValidacionService = Depends(obtener_servicio_validacion),
) -> List[ResultadoValidacionDominio]:
    """
    Ejecuta validación completa del formulario:
      1. Contraste de documentos adjuntos vs datos diligenciados (vía IA).
      2. Verificación de fechas y vigencias documentales.
      3. Consistencia de información financiera.
      4. Búsqueda en listas de cautela (empresa y representante legal).
    """
    return await servicio.ejecutar_validacion_completa(formulario_id)
