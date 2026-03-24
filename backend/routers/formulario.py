import json
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Formulario, DocumentoAdjunto, EstadoFormulario
from schemas import (
    FormularioCreate, FormularioUpdate, FormularioResponse,
    FormularioConDetalles, DocumentoResponse,
    ResultadoValidacionEnvio, ErrorValidacion
)
from services.bedrock_extractor import PREFILL_MAPPING

router = APIRouter(prefix="/api/formularios", tags=["formularios"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _serialize_json_fields(data: dict) -> dict:
    """Convierte listas/dicts a JSON strings para almacenar en DB."""
    json_fields = [
        "junta_directiva", "accionistas", "referencias_comerciales",
        "referencias_bancarias", "clasificaciones"
    ]
    for field in json_fields:
        if field in data and data[field] is not None:
            if isinstance(data[field], (list, dict)):
                items = data[field]
                serialized = []
                for item in items:
                    if hasattr(item, "model_dump"):
                        serialized.append(item.model_dump())
                    else:
                        serialized.append(item)
                data[field] = json.dumps(serialized, ensure_ascii=False)
    return data


def _deserialize_json_fields(formulario: Formulario) -> dict:
    """Convierte JSON strings de la DB a dicts/listas."""
    data = {}
    for column in formulario.__table__.columns:
        data[column.name] = getattr(formulario, column.name)

    json_fields = [
        "junta_directiva", "accionistas", "referencias_comerciales",
        "referencias_bancarias", "clasificaciones", "tipos_transaccion"
    ]
    for field in json_fields:
        if field in data and data[field] is not None:
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return data


# --- Campos requeridos para envío final ---
CAMPOS_REQUERIDOS_BASE = [
    ("tipo_contraparte", "Tipo de Contraparte"),
    ("tipo_persona", "Tipo de Persona"),
    ("tipo_solicitud", "Tipo de Solicitud"),
    ("razon_social", "Nombre o Razón Social"),
    ("tipo_identificacion", "Tipo de Identificación"),
    ("numero_identificacion", "Número de Identificación"),
    ("direccion", "Dirección"),
    ("departamento", "Departamento"),
    ("ciudad", "Ciudad"),
    ("telefono", "Teléfono"),
    ("correo", "Correo Electrónico"),
    ("nombre_representante", "Nombres y Apellidos del Representante"),
    ("tipo_doc_representante", "Tipo de Documento del Representante"),
    ("numero_doc_representante", "Número de Documento del Representante"),
    ("fecha_expedicion", "Fecha de Expedición"),
    ("ciudad_expedicion", "Ciudad de Expedición"),
    ("nacionalidad", "Nacionalidad"),
    ("fecha_nacimiento", "Fecha de Nacimiento"),
    ("ciudad_nacimiento", "Ciudad de Nacimiento"),
    ("profesion", "Profesión"),
    ("correo_representante", "Correo del Representante"),
    ("telefono_representante", "Teléfono del Representante"),
    ("direccion_funciones", "Dirección donde ejerce funciones"),
    ("ciudad_funciones", "Ciudad donde ejerce funciones"),
    ("actividad_economica", "Actividad Económica Principal"),
    ("codigo_ciiu", "Código CIIU"),
    ("ingresos_mensuales", "Ingresos Mensuales"),
    ("egresos_mensuales", "Egresos Mensuales"),
    ("total_activos", "Total Activos"),
    ("total_pasivos", "Total Pasivos"),
    ("patrimonio", "Patrimonio"),
    ("contacto_ordenes_nombre", "Nombre contacto órdenes"),
    ("contacto_ordenes_cargo", "Cargo contacto órdenes"),
    ("contacto_ordenes_telefono", "Teléfono contacto órdenes"),
    ("contacto_ordenes_correo", "Correo contacto órdenes"),
    ("contacto_pagos_nombre", "Nombre contacto pagos"),
    ("contacto_pagos_cargo", "Cargo contacto pagos"),
    ("contacto_pagos_telefono", "Teléfono contacto pagos"),
    ("contacto_pagos_correo", "Correo contacto pagos"),
    ("entidad_bancaria", "Entidad Bancaria"),
    ("ciudad_banco", "Ciudad Banco"),
    ("tipo_cuenta", "Tipo de Cuenta"),
    ("numero_cuenta", "Número de Cuenta"),
    ("origen_fondos", "Origen de Fondos"),
    ("nombre_firma", "Nombre para Firma"),
    ("fecha_firma", "Fecha de Firma"),
    ("ciudad_firma", "Ciudad de Firma"),
]


def _validar_campos_requeridos(formulario: Formulario) -> List[ErrorValidacion]:
    """Valida que todos los campos requeridos estén diligenciados."""
    errores = []
    for campo, nombre in CAMPOS_REQUERIDOS_BASE:
        valor = getattr(formulario, campo, None)
        if valor is None or (isinstance(valor, str) and valor.strip() == ""):
            errores.append(ErrorValidacion(
                campo=campo,
                mensaje=f"El campo '{nombre}' es obligatorio"
            ))

    # Validar autorizaciones
    if not formulario.autorizacion_datos:
        errores.append(ErrorValidacion(
            campo="autorizacion_datos",
            mensaje="Debe aceptar la autorización de tratamiento de datos"
        ))
    if not formulario.declaracion_origen_fondos:
        errores.append(ErrorValidacion(
            campo="declaracion_origen_fondos",
            mensaje="Debe aceptar la declaración de origen de fondos"
        ))

    return errores


# === ENDPOINTS ===

@router.post("/", response_model=FormularioResponse)
def crear_formulario(data: FormularioCreate, db: Session = Depends(get_db)):
    """Crear un nuevo formulario (comienza como borrador)."""
    form_data = data.model_dump(exclude_unset=True)
    form_data = _serialize_json_fields(form_data)

    formulario = Formulario(**form_data)
    db.add(formulario)
    db.commit()
    db.refresh(formulario)
    return formulario


@router.get("/{codigo}", response_model=FormularioConDetalles)
def obtener_formulario(codigo: str, db: Session = Depends(get_db)):
    """Obtener formulario por código de petición o ID."""
    formulario = db.query(Formulario).filter(
        (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
    ).first()

    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    data = _deserialize_json_fields(formulario)
    data["documentos"] = [
        DocumentoResponse(
            id=d.id, tipo_documento=d.tipo_documento,
            nombre_archivo=d.nombre_archivo,
            content_type=d.content_type, tamano=d.tamano,
            created_at=d.created_at
        ) for d in formulario.documentos
    ]
    data["validaciones"] = [
        {
            "id": v.id, "tipo": v.tipo, "campo": v.campo,
            "resultado": v.resultado, "detalle": v.detalle,
            "valor_formulario": v.valor_formulario,
            "valor_documento": v.valor_documento,
            "created_at": v.created_at
        } for v in formulario.validaciones
    ]
    return data


@router.put("/{id}", response_model=FormularioResponse)
def actualizar_formulario(id: str, data: FormularioUpdate, db: Session = Depends(get_db)):
    """Actualizar formulario (guardado parcial). Solo si está en borrador."""
    formulario = db.query(Formulario).filter(Formulario.id == id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    if formulario.estado != EstadoFormulario.BORRADOR:
        raise HTTPException(
            status_code=400,
            detail="No se puede modificar un formulario que ya fue enviado"
        )

    update_data = data.model_dump(exclude_unset=True)
    update_data = _serialize_json_fields(update_data)

    for key, value in update_data.items():
        setattr(formulario, key, value)

    db.commit()
    db.refresh(formulario)
    return formulario


@router.post("/{id}/enviar", response_model=ResultadoValidacionEnvio)
def enviar_formulario(id: str, db: Session = Depends(get_db)):
    """Envío final del formulario. Valida campos requeridos y bloquea edición."""
    formulario = db.query(Formulario).filter(Formulario.id == id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    if formulario.estado != EstadoFormulario.BORRADOR:
        raise HTTPException(
            status_code=400,
            detail="El formulario ya fue enviado previamente"
        )

    # Validar campos requeridos
    errores = _validar_campos_requeridos(formulario)
    if errores:
        return ResultadoValidacionEnvio(valido=False, errores=errores)

    # Marcar como enviado
    formulario.estado = EstadoFormulario.ENVIADO
    db.commit()

    return ResultadoValidacionEnvio(valido=True, errores=[])


@router.post("/{id}/documentos", response_model=DocumentoResponse)
async def subir_documento(
    id: str,
    request: Request,
    tipo_documento: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Sube un documento y extrae sus datos con IA de forma inmediata.

    Flujo event-driven: cada upload dispara UNA sola llamada a Bedrock
    para el tipo_documento recibido. No itera sobre otros documentos.
    """
    formulario = db.query(Formulario).filter(Formulario.id == id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    if formulario.estado != EstadoFormulario.BORRADOR:
        raise HTTPException(
            status_code=400,
            detail="No se pueden agregar documentos a un formulario enviado"
        )

    # 1. Guardar archivo en disco
    form_upload_dir = os.path.join(UPLOAD_DIR, id)
    os.makedirs(form_upload_dir, exist_ok=True)

    file_path = os.path.join(form_upload_dir, archivo.filename)
    content = await archivo.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 2. Registrar en DB
    documento = DocumentoAdjunto(
        formulario_id=id,
        tipo_documento=tipo_documento,
        nombre_archivo=archivo.filename,
        ruta_archivo=file_path,
        content_type=archivo.content_type,
        tamano=len(content),
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)

    # 3. Extracción IA — SOLO para este tipo_documento, una sola invocación
    campos_sugeridos: dict = {}
    extractor = request.app.state.orchestrator.extractor
    extraction = await extractor.extract(
        file_path=file_path,
        document_type=tipo_documento,
    )
    if extraction.extraido:
        campos_sugeridos = _map_prefill_fields(tipo_documento, extraction.datos)

    # Retornar documento + campos sugeridos para que el frontend los aplique
    response = DocumentoResponse(
        id=documento.id,
        tipo_documento=documento.tipo_documento,
        nombre_archivo=documento.nombre_archivo,
        content_type=documento.content_type,
        tamano=documento.tamano,
        created_at=documento.created_at,
        campos_sugeridos=campos_sugeridos if campos_sugeridos else None,
    )
    return response


@router.delete("/{id}/documentos/{doc_id}")
def eliminar_documento(id: str, doc_id: str, db: Session = Depends(get_db)):
    """Eliminar un documento adjunto."""
    documento = db.query(DocumentoAdjunto).filter(
        DocumentoAdjunto.id == doc_id,
        DocumentoAdjunto.formulario_id == id
    ).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Eliminar archivo físico
    if os.path.exists(documento.ruta_archivo):
        os.remove(documento.ruta_archivo)

    db.delete(documento)
    db.commit()

    return {"message": "Documento eliminado"}


@router.get("/{id}/documentos", response_model=List[DocumentoResponse])
def listar_documentos(id: str, db: Session = Depends(get_db)):
    """Listar documentos adjuntos de un formulario."""
    documentos = db.query(DocumentoAdjunto).filter(
        DocumentoAdjunto.formulario_id == id
    ).all()
    return documentos


@router.post("/{id}/documentos/{doc_id}/prefill")
async def prefill_desde_documento(
    id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Escanea un documento con IA y retorna campos sugeridos para pre-llenar.
    
    Tarea 4 del README: el sistema procesa los adjuntos y sugiere
    valores para el formulario con base en la información extraída.
    """
    documento = db.query(DocumentoAdjunto).filter(
        DocumentoAdjunto.id == doc_id,
        DocumentoAdjunto.formulario_id == id,
    ).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Usar el extractor Bedrock del orchestrator
    orchestrator = request.app.state.orchestrator
    extraction = await orchestrator.extractor.extract(
        file_path=documento.ruta_archivo,
        document_type=documento.tipo_documento,
    )

    if not extraction.extraido:
        return {
            "success": False,
            "message": extraction.mensaje,
            "campos_sugeridos": {},
        }

    # Mapear datos extraídos a campos del formulario
    campos = _map_prefill_fields(documento.tipo_documento, extraction.datos)

    return {
        "success": True,
        "message": extraction.mensaje,
        "confianza": extraction.confianza,
        "datos_extraidos": extraction.datos,
        "campos_sugeridos": campos,
    }


@router.post("/{id}/prefill-all")
async def prefill_todos_documentos(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Escanea TODOS los documentos adjuntos y retorna campos consolidados
    para pre-llenar el formulario completo.
    """
    formulario = db.query(Formulario).filter(Formulario.id == id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")

    orchestrator = request.app.state.orchestrator

    all_fields: dict = {}
    detalles: list = []

    for doc in formulario.documentos:
        extraction = await orchestrator.extractor.extract(
            file_path=doc.ruta_archivo,
            document_type=doc.tipo_documento,
        )

        campos = {}
        if extraction.extraido:
            campos = _map_prefill_fields(doc.tipo_documento, extraction.datos)
            for k, v in campos.items():
                if k not in all_fields and v is not None:
                    all_fields[k] = v

        detalles.append({
            "documento": doc.nombre_archivo,
            "tipo": doc.tipo_documento,
            "extraido": extraction.extraido,
            "campos_sugeridos": campos,
            "confianza": extraction.confianza,
        })

    return {
        "success": True,
        "campos_consolidados": all_fields,
        "detalles_por_documento": detalles,
    }


def _map_prefill_fields(document_type: str, extracted_data: dict) -> dict:
    """Mapea datos extraídos del documento a campos del formulario."""
    mapping = PREFILL_MAPPING.get(document_type, {})
    return {
        form_field: extracted_data[doc_field]
        for doc_field, form_field in mapping.items()
        if extracted_data.get(doc_field) is not None
    }

