"""
Router de formularios — responsabilidades HTTP exclusivamente.

SRP : parsea solicitudes, delega al servicio y devuelve respuestas.
      Toda la lógica de negocio vive en FormularioService.
DIP : depende de la abstracción ExtractorIAImp, no de la implementación Bedrock.
"""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from dependencies import obtener_config, obtener_extractor
from schemas import (
    CredencialesAccesoManual,
    CredencialesEnvioFormulario,
    DocumentoResponse,
    FormularioConDetalles,
    FormularioCreate,
    FormularioResponse,
    FormularioUpdate,
    ResultadoValidacionEnvio,
)
from core.contratos import ExtractorIAImp
from core.configuracion import AppConfig
from core.limitador import limitador
from services.formulario.formulario_service import FormularioService
from services.acceso_manual.acceso_manual_service import AccesoManualService
from routers.transformers import construir_respuesta_documento

enrutador = APIRouter(prefix="/api/formularios", tags=["formularios"])


# ─── Fábrica de dependencias ─────────────────────────────────────────────────

def obtener_servicio_formulario(
    sesion: Session = Depends(get_db),
    extractor: ExtractorIAImp = Depends(obtener_extractor),
    config: AppConfig = Depends(obtener_config),
) -> FormularioService:
    """Crea un FormularioService con las dependencias inyectadas."""
    return FormularioService(sesion, extractor, config.upload_dir)


def obtener_servicio_acceso(
    sesion: Session = Depends(get_db),
    config: AppConfig = Depends(obtener_config),
) -> AccesoManualService:
    return AccesoManualService(sesion, config.frontend_urls[0])


# ─── Recuperación de sesión ──────────────────────────────────────────────────
# IMPORTANTE: esta ruta debe declararse ANTES de /{formulario_id} para que
# FastAPI no capture "/sesion/recuperar-por-acceso" como un valor de {formulario_id}.


@enrutador.post(
    "/sesion/recuperar-por-acceso",
    response_model=FormularioConDetalles,
    responses={
        401: {"description": "Código de petición o PIN incorrecto"},
        409: {"description": "El formulario ya fue enviado y no está disponible para recuperación"},
        410: {"description": "El acceso ha expirado"},
        429: {"description": "Demasiados intentos. Espere un momento antes de reintentar"},
    },
)
@limitador.limit("5/minute")
def recuperar_sesion_por_acceso_manual(
    request: Request,
    credenciales: CredencialesAccesoManual,
    servicio: AccesoManualService = Depends(obtener_servicio_acceso),
) -> FormularioConDetalles:
    """
    Recupera un borrador activo mediante el par (código de petición + PIN).

    Flujo de recuperación soportado para formularios creados a través del
    portal interno de acceso manual.

    Respuestas:
      200 — Formulario encontrado; cuerpo contiene el borrador completo.
      401 — Código de petición o PIN incorrecto (error intencionalmente genérico).
      409 — El formulario ya fue enviado; no es recuperable como borrador.
    """
    return servicio.buscar_formulario_por_credenciales(
        credenciales.codigo_peticion,
        credenciales.pin,
    )


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


@enrutador.post(
    "/{formulario_id}/enviar",
    response_model=ResultadoValidacionEnvio,
    responses={
        410: {"description": "El acceso ha expirado"},
        429: {"description": "Demasiados intentos. Espere un momento antes de reintentar"},
    },
)
@limitador.limit("10/minute")
def enviar_formulario(
    request: Request,
    formulario_id: str,
    credenciales: Optional[CredencialesEnvioFormulario] = Body(None),
    servicio_acceso: AccesoManualService = Depends(obtener_servicio_acceso),
    servicio: FormularioService = Depends(obtener_servicio_formulario),
) -> ResultadoValidacionEnvio:
    """
    Envío final del formulario. Valida campos requeridos y bloquea edición posterior.

    Si el formulario fue creado via acceso manual, requiere credenciales
    (token de diligenciamiento o código+PIN) para autorizar el envío.
    """
    servicio_acceso.verificar_credenciales_si_aplica(
        formulario_id,
        token=credenciales.token_diligenciamiento if credenciales else None,
        codigo_peticion=credenciales.codigo_peticion if credenciales else None,
        pin=credenciales.pin if credenciales else None,
    )
    resultado = servicio.enviar(formulario_id)
    if (
        resultado.valido
        and credenciales is not None
        and credenciales.token_diligenciamiento is not None
    ):
        servicio_acceso.consumir_token_al_enviar(
            formulario_id,
            credenciales.token_diligenciamiento,
        )
    return resultado


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
