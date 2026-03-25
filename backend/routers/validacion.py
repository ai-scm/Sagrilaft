"""
Router de validación de formularios.

Usa el DocumentValidationOrchestrator inyectado en app.state
para ejecutar extracción IA + validación de documentos + listas de cautela.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Formulario, ResultadoValidacion
from schemas import ValidacionResponse
from services.lista_cautela_service import ListaCautelaService

router = APIRouter(prefix="/api/validar", tags=["validación"])


def _get_orchestrator(request: Request):
    """Obtiene el orquestador inyectado via app.state (DI)."""
    return request.app.state.orchestrator


def _get_lista_cautela_service(request: Request) -> ListaCautelaService:
    """Obtiene el servicio de listas de cautela inyectado via app.state (DI)."""
    return request.app.state.lista_cautela_service


@router.post("/{id}", response_model=List[ValidacionResponse])
async def validar_formulario(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Ejecuta validación completa del formulario:
    1. Contraste documentos adjuntos vs datos diligenciados (via IA)
    2. Verificación de fechas y vigencias
    3. Consistencia información financiera
    4. Búsqueda en listas de cautela
    """
    formulario = db.query(Formulario).filter(Formulario.id == id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    # Limpiar validaciones previas
    db.query(ResultadoValidacion).filter(
        ResultadoValidacion.formulario_id == id
    ).delete()

    # Datos del formulario para contraste
    form_data = {
        "razon_social": formulario.razon_social,
        "numero_identificacion": formulario.numero_identificacion,
        "nombre_representante": formulario.nombre_representante,
        "numero_doc_representante": formulario.numero_doc_representante,
        "total_activos": formulario.total_activos,
        "total_pasivos": formulario.total_pasivos,
        "patrimonio": formulario.patrimonio,
        "ingresos_mensuales": formulario.ingresos_mensuales,
        "egresos_mensuales": formulario.egresos_mensuales,
        "codigo_ciiu": formulario.codigo_ciiu,
    }

    orchestrator = _get_orchestrator(request)
    lista_cautela_service = _get_lista_cautela_service(request)
    todos_hallazgos: list[ResultadoValidacion] = []

    # ── 1. Validación de documentos via IA ──────────────
    documentos_lista = [
        {"file_path": doc.ruta_archivo, "document_type": doc.tipo_documento}
        for doc in formulario.documentos
    ]
    individual_findings, cross_findings = await orchestrator.validate_all_documents(
        documents=documentos_lista,
        form_data=form_data,
    )

    for f in individual_findings:
        resultado_db = ResultadoValidacion(
            formulario_id=id,
            tipo="documento",
            campo=f.campo,
            resultado=f.resultado,
            detalle=f.detalle,
            valor_formulario=f.valor_formulario,
            valor_documento=f.valor_documento,
        )
        db.add(resultado_db)
        todos_hallazgos.append(resultado_db)

    for f in cross_findings:
        resultado_db = ResultadoValidacion(
            formulario_id=id,
            tipo="cruce_documentos",
            campo=f.campo,
            resultado=f.resultado,
            detalle=f.detalle,
            valor_formulario=f.valor_formulario,
            valor_documento=f.valor_documento,
        )
        db.add(resultado_db)
        todos_hallazgos.append(resultado_db)

    # ── 2. Listas de cautela: razón social ──────────────
    if formulario.razon_social:
        resultados_listas = lista_cautela_service.buscar_todas_listas(
            formulario.razon_social,
            formulario.numero_identificacion,
        )
        for r in resultados_listas:
            resultado_db = ResultadoValidacion(
                formulario_id=id,
                tipo="lista_cautela",
                campo=r.lista,
                resultado="error" if r.encontrado else "ok",
                detalle=r.detalle,
            )
            db.add(resultado_db)
            todos_hallazgos.append(resultado_db)

    # ── 3. Listas de cautela: representante legal ───────
    if formulario.nombre_representante:
        resultados_rep = lista_cautela_service.buscar_todas_listas(
            formulario.nombre_representante,
            formulario.numero_doc_representante,
        )
        for r in resultados_rep:
            resultado_db = ResultadoValidacion(
                formulario_id=id,
                tipo="lista_cautela",
                campo=f"{r.lista} (Rep. Legal)",
                resultado="error" if r.encontrado else "ok",
                detalle=r.detalle,
            )
            db.add(resultado_db)
            todos_hallazgos.append(resultado_db)

    db.commit()

    for h in todos_hallazgos:
        db.refresh(h)

    return todos_hallazgos
