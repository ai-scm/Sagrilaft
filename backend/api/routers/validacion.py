"""
Router de validación de formularios.

Responsabilidad exclusiva: recibir la solicitud HTTP, delegar al ValidacionService
y traducir excepciones de dominio a respuestas HTTP apropiadas.

SRP : sin lógica de negocio ni orquestación — esa vive en ValidacionService.
DIP : depende de ValidacionService vía inyección de dependencias.
"""

from typing import List

from fastapi import APIRouter, Depends

from infrastructure.dependencies import (
    obtener_orquestador,
    obtener_repo_validacion,
    obtener_servicio_lista_cautela,
)
from infrastructure.persistencia.repositorios import RepositorioValidacionSQLAlchemy
from api.schemas import ValidacionResponse
from domain.validacion.resultado import ResultadoValidacionDominio
from services.validacion.orquestador import OrquestadorValidacionDocumentos
from services.listas.servicio_listas_cautela import ListaCautelaService
from services.validacion.validacion_service import ValidacionService

enrutador = APIRouter(prefix="/api/validar", tags=["validación"])


# ─── Fábrica de dependencias ─────────────────────────────────────────────────

def obtener_servicio_validacion(
    repo: RepositorioValidacionSQLAlchemy = Depends(obtener_repo_validacion),
    orquestador: OrquestadorValidacionDocumentos = Depends(obtener_orquestador),
    servicio_listas: ListaCautelaService = Depends(obtener_servicio_lista_cautela),
) -> ValidacionService:
    """Construye el ValidacionService con las dependencias inyectadas."""
    return ValidacionService(repo, orquestador, servicio_listas)


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
