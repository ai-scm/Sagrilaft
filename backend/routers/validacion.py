"""
Router de validación de formularios.

Orquesta la validación completa de un formulario SAGRILAFT:
  1. Contraste de documentos adjuntos vs datos diligenciados (vía IA).
  2. Búsqueda en listas de cautela para la empresa y el representante legal.

SRP : cada función privada tiene una responsabilidad única y delimitada.
OCP : agregar nuevos tipos de validación no requiere modificar el endpoint principal.
DIP : depende del orquestador y del servicio de listas vía inyección de dependencias.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import obtener_orquestador, obtener_servicio_lista_cautela
from models import Formulario, ResultadoValidacion
from schemas import ValidacionResponse
from services.contracts import ValidationFinding
from services.document_orchestrator import DocumentValidationOrchestrator
from services.lista_cautela_service import ListaCautelaService

enrutador = APIRouter(prefix="/api/validar", tags=["validación"])


# ─── Endpoint principal ───────────────────────────────────────────────────────

@enrutador.post("/{formulario_id}", response_model=List[ValidacionResponse])
async def validar_formulario(
    formulario_id: str,
    sesion: Session = Depends(get_db),
    orquestador: DocumentValidationOrchestrator = Depends(obtener_orquestador),
    servicio_listas: ListaCautelaService = Depends(obtener_servicio_lista_cautela),
) -> List[ValidacionResponse]:
    """
    Ejecuta validación completa del formulario:
      1. Contraste de documentos adjuntos vs datos diligenciados (vía IA).
      2. Verificación de fechas y vigencias documentales.
      3. Consistencia de información financiera.
      4. Búsqueda en listas de cautela (empresa y representante legal).
    """
    formulario = _obtener_formulario_o_404(sesion, formulario_id)
    _limpiar_validaciones_previas(sesion, formulario_id)

    hallazgos: List[ResultadoValidacion] = []
    hallazgos += await _validar_documentos(sesion, orquestador, formulario_id, formulario)
    hallazgos += _validar_listas_cautela(sesion, servicio_listas, formulario_id, formulario)

    sesion.commit()
    for hallazgo in hallazgos:
        sesion.refresh(hallazgo)

    return hallazgos


# ─── Helpers de orquestación ─────────────────────────────────────────────────

def _obtener_formulario_o_404(sesion: Session, formulario_id: str) -> Formulario:
    """Recupera el formulario desde la base de datos o lanza HTTP 404."""
    formulario = sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    return formulario


def _limpiar_validaciones_previas(sesion: Session, formulario_id: str) -> None:
    """Elimina todos los resultados de validaciones anteriores del formulario."""
    sesion.query(ResultadoValidacion).filter(
        ResultadoValidacion.formulario_id == formulario_id
    ).delete()


async def _validar_documentos(
    sesion: Session,
    orquestador: DocumentValidationOrchestrator,
    formulario_id: str,
    formulario: Formulario,
) -> List[ResultadoValidacion]:
    """
    Valida los documentos adjuntos vía IA y persiste los hallazgos en sesión.

    Retorna los ResultadoValidacion creados (sin commit, para atomicidad).
    """
    datos_formulario = _extraer_datos_relevantes(formulario)
    lista_documentos = [
        {"file_path": doc.ruta_archivo, "document_type": doc.tipo_documento}
        for doc in formulario.documentos
    ]

    hallazgos_individuales, hallazgos_cruzados = await orquestador.validate_all_documents(
        documents=lista_documentos,
        form_data=datos_formulario,
    )

    resultados: List[ResultadoValidacion] = []

    for hallazgo in hallazgos_individuales:
        resultado = _hallazgo_a_resultado(formulario_id, "documento", hallazgo)
        sesion.add(resultado)
        resultados.append(resultado)

    for hallazgo in hallazgos_cruzados:
        resultado = _hallazgo_a_resultado(formulario_id, "cruce_documentos", hallazgo)
        sesion.add(resultado)
        resultados.append(resultado)

    return resultados


def _validar_listas_cautela(
    sesion: Session,
    servicio_listas: ListaCautelaService,
    formulario_id: str,
    formulario: Formulario,
) -> List[ResultadoValidacion]:
    """
    Busca la empresa y el representante legal en todas las listas de cautela
    y persiste los resultados en sesión.

    Retorna los ResultadoValidacion creados (sin commit, para atomicidad).
    """
    resultados: List[ResultadoValidacion] = []

    if formulario.razon_social:
        resultados += _registrar_busqueda_en_listas(
            sesion=sesion,
            servicio_listas=servicio_listas,
            formulario_id=formulario_id,
            nombre=formulario.razon_social,
            numero_identificacion=formulario.numero_identificacion,
            sufijo_campo=None,
        )

    if formulario.nombre_representante:
        resultados += _registrar_busqueda_en_listas(
            sesion=sesion,
            servicio_listas=servicio_listas,
            formulario_id=formulario_id,
            nombre=formulario.nombre_representante,
            numero_identificacion=formulario.numero_doc_representante,
            sufijo_campo="(Rep. Legal)",
        )

    return resultados


# ─── Helpers de transformación ────────────────────────────────────────────────

def _extraer_datos_relevantes(formulario: Formulario) -> Dict[str, Any]:
    """Extrae los campos del formulario necesarios para la validación documental."""
    return {
        "razon_social":             formulario.razon_social,
        "numero_identificacion":    formulario.numero_identificacion,
        "nombre_representante":     formulario.nombre_representante,
        "numero_doc_representante": formulario.numero_doc_representante,
        "total_activos":            formulario.total_activos,
        "total_pasivos":            formulario.total_pasivos,
        "patrimonio":               formulario.patrimonio,
        "ingresos_mensuales":       formulario.ingresos_mensuales,
        "egresos_mensuales":        formulario.egresos_mensuales,
        "codigo_ciiu":              formulario.codigo_ciiu,
    }


def _hallazgo_a_resultado(
    formulario_id: str,
    tipo: str,
    hallazgo: ValidationFinding,
) -> ResultadoValidacion:
    """Convierte un ValidationFinding en un ResultadoValidacion persistible en BD."""
    return ResultadoValidacion(
        formulario_id=formulario_id,
        tipo=tipo,
        campo=hallazgo.campo,
        resultado=hallazgo.resultado,
        detalle=hallazgo.detalle,
        valor_formulario=hallazgo.valor_formulario,
        valor_documento=hallazgo.valor_documento,
    )


def _registrar_busqueda_en_listas(
    sesion: Session,
    servicio_listas: ListaCautelaService,
    formulario_id: str,
    nombre: str,
    numero_identificacion: Optional[str],
    sufijo_campo: Optional[str],
) -> List[ResultadoValidacion]:
    """
    Ejecuta la búsqueda en listas de cautela para un sujeto y registra cada
    resultado en la sesión.

    Args:
        sufijo_campo: Texto adicional para distinguir empresa de representante
                      en el nombre del campo (ej. "(Rep. Legal)"). None para empresa.
    """
    resultados_listas = servicio_listas.buscar_todas_listas(nombre, numero_identificacion)
    nuevos: List[ResultadoValidacion] = []

    for resultado_lista in resultados_listas:
        nombre_campo = (
            f"{resultado_lista.lista} {sufijo_campo}"
            if sufijo_campo
            else resultado_lista.lista
        )
        resultado = ResultadoValidacion(
            formulario_id=formulario_id,
            tipo="lista_cautela",
            campo=nombre_campo,
            resultado="error" if resultado_lista.encontrado else "ok",
            detalle=resultado_lista.detalle,
        )
        sesion.add(resultado)
        nuevos.append(resultado)

    return nuevos
