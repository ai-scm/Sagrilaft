"""
FormularioService — lógica de negocio para formularios SAGRILAFT.

Organiza responsabilidades en capas claras:
  - Funciones de serialización JSON: delegadas a serializacion.py
  - ValidadorEnvioFormulario: delegado a validacion.py
  - DocumentoService: maneja CRUD y sistema de archivos de adjuntos.
  - AnalisisDocumentosService: orquesta extracción de datos vía IA.
  - FormularioService: CRUD de formularios e integración (Facade).
"""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import DocumentoAdjunto, EstadoFormulario, Formulario
from schemas import (
    DocumentoResponse,
    FormularioCreate,
    FormularioUpdate,
    ResultadoValidacionEnvio,
)
from core.contratos import IExtractorIA
from services.formulario.serializacion import serializar_campos_json, deserializar_campos_json
from services.formulario.validacion import ValidadorEnvioFormulario
from services.formulario.documento_service import DocumentoService
from services.formulario.analisis_service import AnalisisDocumentosService, ResultadoGuardadoDocumento


class FormularioYaEnviadoError(Exception):
    """
    Se lanza cuando las credenciales identifican un formulario que ya fue
    enviado y, por tanto, no es recuperable como borrador activo.
    """


class FormularioService:
    """
    Servicio de negocio para la gestión de formularios SAGRILAFT.

    Actúa como Facade conectando el CRUD de formulario con la validación,
    los documentos y el análisis de IA. Mantiene la interfaz pública intacta.
    """

    def __init__(self, sesion: Session, extractor: IExtractorIA) -> None:
        self._sesion = sesion
        self._validador_envio = ValidadorEnvioFormulario()
        self._documentos = DocumentoService(sesion)
        self._analisis = AnalisisDocumentosService(extractor)

    # ─── CRUD de formulario ───────────────────────────────────────────────────

    def crear_borrador(self, datos: FormularioCreate) -> Dict[str, Any]:
        datos_dict = serializar_campos_json(datos.model_dump(exclude_unset=True))
        formulario = Formulario(**datos_dict)
        self._sesion.add(formulario)
        self._sesion.commit()
        self._sesion.refresh(formulario)
        return deserializar_campos_json(formulario)

    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        formulario = self._sesion.query(Formulario).filter(
            (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        datos = deserializar_campos_json(formulario)
        datos["documentos"] = self._documentos_a_respuesta(formulario.documentos)
        datos["validaciones"] = self._validaciones_a_dict(formulario.validaciones)
        return datos

    def actualizar(self, formulario_id: str, datos: FormularioUpdate) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(
            formulario,
            "No se puede modificar un formulario que ya fue enviado",
        )

        datos_actualizacion = serializar_campos_json(datos.model_dump(exclude_unset=True))
        for clave, valor in datos_actualizacion.items():
            setattr(formulario, clave, valor)

        self._sesion.commit()
        self._sesion.refresh(formulario)
        return deserializar_campos_json(formulario)

    def buscar_borrador_por_credenciales(
        self, correo: str, numero_identificacion: str
    ) -> Optional[Dict[str, Any]]:
        _filtro_nit = or_(
            Formulario.numero_identificacion == numero_identificacion,
            func.concat(
                Formulario.numero_identificacion,
                Formulario.digito_verificacion,
            ) == numero_identificacion,
        )

        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.correo == correo, _filtro_nit)
            .order_by(Formulario.updated_at.desc())
            .first()
        )

        if not formulario:
            return None

        if formulario.estado != EstadoFormulario.BORRADOR:
            raise FormularioYaEnviadoError()

        datos = deserializar_campos_json(formulario)
        datos["documentos"] = self._documentos_a_respuesta(formulario.documentos)
        datos["validaciones"] = self._validaciones_a_dict(formulario.validaciones)
        return datos

    def enviar(self, formulario_id: str) -> ResultadoValidacionEnvio:
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(formulario, "El formulario ya fue enviado previamente")

        errores = self._validador_envio.validar(formulario)
        if errores:
            return ResultadoValidacionEnvio(valido=False, errores=errores)

        formulario.estado = EstadoFormulario.ENVIADO
        self._sesion.commit()
        return ResultadoValidacionEnvio(valido=True, errores=[])

    # ─── Gestión de documentos adjuntos ──────────────────────────────────────

    async def guardar_documento(
        self,
        formulario_id: str,
        tipo_documento: str,
        contenido_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
    ) -> ResultadoGuardadoDocumento:
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(
            formulario,
            "No se pueden agregar documentos a un formulario enviado",
        )

        ruta_archivo = self._documentos.guardar_archivo_en_disco(
            formulario_id, nombre_archivo, contenido_bytes
        )
        documento = self._documentos.registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            ruta_archivo=ruta_archivo,
            content_type=content_type,
            tamano=len(contenido_bytes),
        )

        return await self._analisis.analizar_nueva_carga(
            documento=documento,
            formulario=formulario
        )

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        self._documentos.eliminar_documento(formulario_id, doc_id)

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        return self._documentos.listar_documentos(formulario_id)

    # ─── Pre-llenado con IA ───────────────────────────────────────────────────

    async def prellenar_documento(
        self, formulario_id: str, doc_id: str
    ) -> Dict[str, Any]:
        documento = self._documentos.buscar_documento_o_404(formulario_id, doc_id)
        return await self._analisis.prellenar_documento(documento)

    async def prellenar_todos(self, formulario_id: str) -> Dict[str, Any]:
        """Solo es invocado en estado borrador, el router valida internamente si es posible"""
        self._buscar_formulario_o_404(formulario_id)
        documentos = self._documentos.listar_documentos(formulario_id)
        return await self._analisis.prellenar_multiples_documentos(documentos)

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _buscar_formulario_o_404(self, formulario_id: str) -> Formulario:
        formulario = self._sesion.query(Formulario).filter(
            Formulario.id == formulario_id
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")
        return formulario

    def _verificar_estado_borrador(
        self, formulario: Formulario, mensaje_error: str
    ) -> None:
        if formulario.estado != EstadoFormulario.BORRADOR:
            raise HTTPException(status_code=400, detail=mensaje_error)

    @staticmethod
    def _documentos_a_respuesta(
        documentos: List[DocumentoAdjunto],
    ) -> List[DocumentoResponse]:
        return [
            DocumentoResponse(
                id=d.id,
                tipo_documento=d.tipo_documento,
                nombre_archivo=d.nombre_archivo,
                content_type=d.content_type,
                tamano=d.tamano,
                created_at=d.created_at,
            )
            for d in documentos if d.deleted_at is None
        ]

    @staticmethod
    def _validaciones_a_dict(validaciones: List[Any]) -> List[Dict[str, Any]]:
        return [
            {
                "id":              v.id,
                "tipo":            v.tipo,
                "campo":           v.campo,
                "resultado":       v.resultado,
                "detalle":         v.detalle,
                "valor_formulario":v.valor_formulario,
                "valor_documento": v.valor_documento,
                "created_at":      v.created_at,
            }
            for v in validaciones
        ]
