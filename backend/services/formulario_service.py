"""
FormularioService — lógica de negocio para formularios SAGRILAFT.

SRP: toda la lógica de negocio relacionada con formularios vive aquí,
separada de las responsabilidades HTTP del router.
"""

import json
from pathlib import Path
from typing import List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Formulario, DocumentoAdjunto, EstadoFormulario
from schemas import (
    FormularioCreate, FormularioUpdate, FormularioResponse,
    DocumentoResponse, ResultadoValidacionEnvio, ErrorValidacion
)
from services.bedrock_extractor import PREFILL_MAPPING
from services.contracts import IAIExtractor

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


# Campos requeridos para validación de envío final
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
    ("origen_fondos", "Origen de Fondos"),
    ("nombre_firma", "Nombre para Firma"),
    ("fecha_firma", "Fecha de Firma"),
    ("ciudad_firma", "Ciudad de Firma"),
]


class FormularioService:
    """
    Servicio de negocio para la gestión de formularios SAGRILAFT.

    Encapsula todas las operaciones CRUD, manejo de documentos adjuntos
    y coordinación con el extractor IA, manteniendo los routers libres
    de lógica de negocio.
    """

    def __init__(self, db: Session, extractor: IAIExtractor) -> None:
        """
        Inicializa el servicio con sus dependencias inyectadas.

        Args:
            db: Sesión de base de datos SQLAlchemy.
            extractor: Implementación del extractor IA.
        """
        self.db = db
        self.extractor = extractor

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _serialize_json_fields(self, data: dict) -> dict:
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

    def _deserialize_json_fields(self, formulario: Formulario) -> dict:
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

    def _validar_campos_requeridos(self, formulario: Formulario) -> List[ErrorValidacion]:
        """Valida que todos los campos requeridos estén diligenciados."""
        errores = []
        for campo, nombre in CAMPOS_REQUERIDOS_BASE:
            valor = getattr(formulario, campo, None)
            if valor is None or (isinstance(valor, str) and valor.strip() == ""):
                errores.append(ErrorValidacion(
                    campo=campo,
                    mensaje=f"El campo '{nombre}' es obligatorio"
                ))

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

    def _map_prefill_fields(self, document_type: str, extracted_data: dict) -> dict:
        """Mapea datos extraídos del documento a campos del formulario."""
        mapping = PREFILL_MAPPING.get(document_type, {})
        return {
            form_field: extracted_data[doc_field]
            for doc_field, form_field in mapping.items()
            if extracted_data.get(doc_field) is not None
        }

    # ------------------------------------------------------------------
    # Métodos públicos
    # ------------------------------------------------------------------

    def crear_borrador(self, datos: FormularioCreate) -> Formulario:
        """
        Crea un nuevo formulario en estado borrador.

        Args:
            datos: Datos iniciales del formulario.

        Returns:
            Instancia del formulario recién creado.
        """
        form_data = datos.model_dump(exclude_unset=True)
        form_data = self._serialize_json_fields(form_data)

        formulario = Formulario(**form_data)
        self.db.add(formulario)
        self.db.commit()
        self.db.refresh(formulario)
        return formulario

    def obtener_por_codigo(self, codigo: str) -> dict:
        """
        Obtiene un formulario por código de petición o ID, con documentos
        y validaciones deserializados.

        Args:
            codigo: Código de petición o UUID del formulario.

        Returns:
            Diccionario con los datos del formulario, documentos y validaciones.

        Raises:
            HTTPException 404 si el formulario no existe.
        """
        formulario = self.db.query(Formulario).filter(
            (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
        ).first()

        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        data = self._deserialize_json_fields(formulario)
        data["documentos"] = [
            DocumentoResponse(
                id=d.id,
                tipo_documento=d.tipo_documento,
                nombre_archivo=d.nombre_archivo,
                content_type=d.content_type,
                tamano=d.tamano,
                created_at=d.created_at,
            )
            for d in formulario.documentos
        ]
        data["validaciones"] = [
            {
                "id": v.id,
                "tipo": v.tipo,
                "campo": v.campo,
                "resultado": v.resultado,
                "detalle": v.detalle,
                "valor_formulario": v.valor_formulario,
                "valor_documento": v.valor_documento,
                "created_at": v.created_at,
            }
            for v in formulario.validaciones
        ]
        return data

    def actualizar(self, id: str, datos: FormularioUpdate) -> Formulario:
        """
        Actualiza un formulario en estado borrador (guardado parcial).

        Args:
            id: UUID del formulario.
            datos: Campos a actualizar.

        Returns:
            Instancia del formulario actualizado.

        Raises:
            HTTPException 404 si no se encuentra.
            HTTPException 400 si el formulario ya fue enviado.
        """
        formulario = self.db.query(Formulario).filter(Formulario.id == id).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        if formulario.estado != EstadoFormulario.BORRADOR:
            raise HTTPException(
                status_code=400,
                detail="No se puede modificar un formulario que ya fue enviado"
            )

        update_data = datos.model_dump(exclude_unset=True)
        update_data = self._serialize_json_fields(update_data)

        for key, value in update_data.items():
            setattr(formulario, key, value)

        self.db.commit()
        self.db.refresh(formulario)
        return formulario

    def enviar(self, id: str) -> ResultadoValidacionEnvio:
        """
        Realiza el envío final del formulario, validando campos requeridos
        y bloqueando ediciones posteriores.

        Args:
            id: UUID del formulario.

        Returns:
            Resultado de validación indicando si el envío fue exitoso.

        Raises:
            HTTPException 404 si no se encuentra.
            HTTPException 400 si ya fue enviado previamente.
        """
        formulario = self.db.query(Formulario).filter(Formulario.id == id).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        if formulario.estado != EstadoFormulario.BORRADOR:
            raise HTTPException(
                status_code=400,
                detail="El formulario ya fue enviado previamente"
            )

        errores = self._validar_campos_requeridos(formulario)
        if errores:
            return ResultadoValidacionEnvio(valido=False, errores=errores)

        formulario.estado = EstadoFormulario.ENVIADO
        self.db.commit()

        return ResultadoValidacionEnvio(valido=True, errores=[])

    async def guardar_documento(
        self,
        formulario_id: str,
        tipo_documento: str,
        contenido_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
    ) -> Tuple[DocumentoAdjunto, dict]:
        """
        Guarda un documento en disco y en DB, luego invoca el extractor IA.

        El flujo es event-driven: cada upload dispara UNA sola llamada al
        extractor para el tipo_documento recibido.

        Args:
            formulario_id: UUID del formulario al que pertenece el documento.
            tipo_documento: Tipo de documento (e.g. "cedula_representante").
            contenido_bytes: Contenido binario del archivo.
            nombre_archivo: Nombre original del archivo.
            content_type: MIME type del archivo.

        Returns:
            Tupla (DocumentoAdjunto guardado, dict de campos_sugeridos).

        Raises:
            HTTPException 404 si el formulario no existe.
            HTTPException 400 si el formulario ya fue enviado.
        """
        formulario = self.db.query(Formulario).filter(Formulario.id == formulario_id).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        if formulario.estado != EstadoFormulario.BORRADOR:
            raise HTTPException(
                status_code=400,
                detail="No se pueden agregar documentos a un formulario enviado"
            )

        # 1. Guardar archivo en disco
        form_upload_dir = UPLOAD_DIR / formulario_id
        form_upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = form_upload_dir / nombre_archivo
        file_path.write_bytes(contenido_bytes)

        # 2. Registrar en DB
        documento = DocumentoAdjunto(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            ruta_archivo=str(file_path),
            content_type=content_type,
            tamano=len(contenido_bytes),
        )
        self.db.add(documento)
        self.db.commit()
        self.db.refresh(documento)

        # 3. Extracción IA — solo para este tipo_documento, una sola invocación
        campos_sugeridos: dict = {}
        extraction = await self.extractor.extract(
            file_path=str(file_path),
            document_type=tipo_documento,
        )
        if extraction.extraido:
            campos_sugeridos = self._map_prefill_fields(tipo_documento, extraction.datos)

        return documento, campos_sugeridos

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        """
        Elimina un documento adjunto de disco y de la DB.

        Args:
            formulario_id: UUID del formulario propietario.
            doc_id: UUID del documento a eliminar.

        Raises:
            HTTPException 404 si el documento no existe.
        """
        documento = self.db.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id,
            DocumentoAdjunto.formulario_id == formulario_id,
        ).first()

        if not documento:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        ruta = Path(documento.ruta_archivo)
        if ruta.exists():
            ruta.unlink()

        self.db.delete(documento)
        self.db.commit()

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        """
        Lista todos los documentos adjuntos de un formulario.

        Args:
            formulario_id: UUID del formulario.

        Returns:
            Lista de instancias DocumentoAdjunto.
        """
        return self.db.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.formulario_id == formulario_id
        ).all()

    async def prefill_documento(self, formulario_id: str, doc_id: str) -> dict:
        """
        Escanea un documento con IA y retorna campos sugeridos para pre-llenar
        el formulario.

        Args:
            formulario_id: UUID del formulario propietario.
            doc_id: UUID del documento a procesar.

        Returns:
            Diccionario con success, message, confianza, datos_extraidos y
            campos_sugeridos.

        Raises:
            HTTPException 404 si el documento no existe.
        """
        documento = self.db.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id,
            DocumentoAdjunto.formulario_id == formulario_id,
        ).first()

        if not documento:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        extraction = await self.extractor.extract(
            file_path=documento.ruta_archivo,
            document_type=documento.tipo_documento,
        )

        if not extraction.extraido:
            return {
                "success": False,
                "message": extraction.mensaje,
                "campos_sugeridos": {},
            }

        campos = self._map_prefill_fields(documento.tipo_documento, extraction.datos)

        return {
            "success": True,
            "message": extraction.mensaje,
            "confianza": extraction.confianza,
            "datos_extraidos": extraction.datos,
            "campos_sugeridos": campos,
        }

    async def prefill_todos(self, formulario_id: str) -> dict:
        """
        Escanea TODOS los documentos adjuntos con IA y retorna campos
        consolidados para pre-llenar el formulario completo.

        Args:
            formulario_id: UUID del formulario.

        Returns:
            Diccionario con success, campos_consolidados y
            detalles_por_documento.

        Raises:
            HTTPException 404 si el formulario no existe.
        """
        formulario = self.db.query(Formulario).filter(
            Formulario.id == formulario_id
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        all_fields: dict = {}
        detalles: list = []

        for doc in formulario.documentos:
            extraction = await self.extractor.extract(
                file_path=doc.ruta_archivo,
                document_type=doc.tipo_documento,
            )

            campos = {}
            if extraction.extraido:
                campos = self._map_prefill_fields(doc.tipo_documento, extraction.datos)
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
