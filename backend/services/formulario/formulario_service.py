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
from pathlib import Path

from sqlalchemy.orm import Session

from infrastructure.persistencia.models import DocumentoAdjunto, EstadoFormulario, Formulario
from api.schemas import (
    FormularioCreate,
    FormularioUpdate,
    ResultadoValidacionEnvio,
)
from domain.excepciones import (
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    FormularioYaEnviadoError,
)
from core.contratos import ExtractorIAImp
from services.formulario.serializacion import (
    serializar_campos_json,
    deserializar_campos_json,
    construir_snapshot_formulario,
)
from services.formulario.validacion_envio import ValidadorEnvioFormulario
from services.formulario.documento_service import DocumentoService
from services.formulario.exportacion_pdf import ExportadorFormularioPdf
from services.formulario.almacenamiento_contraparte import (
    resolver_ruta_contraparte,
    crear_carpeta_contraparte,
)
from services.formulario.analisis_service import (
    AnalisisDocumentosService,
    ResultadoGuardadoDocumento,
    obtener_config_analisis_por_defecto,
)
from services.utils.estado_formulario import es_estado_borrador


class FormularioService:
    """
    Servicio de negocio para la gestión de formularios SAGRILAFT.

    Actúa como Facade conectando el CRUD de formulario con la validación,
    los documentos y el análisis de IA. Mantiene la interfaz pública intacta.
    """

    def __init__(self, sesion: Session, extractor: ExtractorIAImp, upload_dir: Path) -> None:
        self._sesion = sesion
        self._validador_envio = ValidadorEnvioFormulario()
        self._documentos = DocumentoService(sesion, upload_dir)
        self._exportador_pdf = ExportadorFormularioPdf(self._documentos)
        self._analisis = AnalisisDocumentosService(
            extractor, 
            obtener_config_analisis_por_defecto()
        )

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
            raise FormularioNoEncontradoError(codigo)

        return construir_snapshot_formulario(formulario)

    def actualizar(self, formulario_id: str, datos: FormularioUpdate) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "No se puede modificar un formulario que ya fue enviado",
        )

        datos_actualizacion = serializar_campos_json(datos.model_dump(exclude_unset=True))
        for clave, valor in datos_actualizacion.items():
            setattr(formulario, clave, valor)

        self._sesion.commit()
        self._sesion.refresh(formulario)
        return deserializar_campos_json(formulario)

    def enviar(self, formulario_id: str) -> ResultadoValidacionEnvio:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "El formulario ya fue enviado previamente",
        )

        errores = self._validador_envio.validar(formulario)
        if errores:
            return ResultadoValidacionEnvio(valido=False, errores=errores)

        ruta_contraparte = resolver_ruta_contraparte(
            formulario.tipo_contraparte,
            formulario.razon_social,
            self._documentos.directorio_base,
        )
        crear_carpeta_contraparte(ruta_contraparte)
        self._documentos.mover_archivos_formulario_a_contraparte(formulario.id, ruta_contraparte)
        self._exportador_pdf.generar_y_guardar_pdf(formulario, ruta_contraparte)

        formulario.estado = EstadoFormulario.ENVIADO.value
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
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "No se pueden agregar documentos a un formulario enviado",
        )

        directorio_borrador = self._documentos.ruta_directorio_borrador(
            formulario.codigo_peticion
        )
        ruta_archivo = self._documentos.guardar_archivo_en_disco(
            directorio_borrador, nombre_archivo, contenido_bytes
        )
        documento = self._documentos.registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=ruta_archivo.name,  # nombre ya sanitizado por guardar_archivo_en_disco
            ruta_archivo=ruta_archivo,
            content_type=content_type,
            tamano=len(contenido_bytes),
        )

        return await self._analisis.analizar_nueva_carga(
            documento=documento,
            formulario=formulario
        )

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "No se pueden eliminar documentos de un formulario enviado",
        )
        self._documentos.eliminar_documento(formulario_id, doc_id)

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        # Para consistencia: si el formulario no existe, se responde 404.
        self._buscar_formulario_o_error(formulario_id)
        return self._documentos.listar_documentos(formulario_id)

    # ─── Pre-llenado con IA ───────────────────────────────────────────────────

    async def prellenar_documento(
        self, formulario_id: str, doc_id: str
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "No se puede prellenar un formulario que ya fue enviado",
        )
        # El router traduce DocumentoNoEncontradoError -> 404.
        documento = self._documentos.buscar_documento(formulario_id, doc_id)
        return await self._analisis.prellenar_documento(documento)

    async def prellenar_todos(self, formulario_id: str) -> Dict[str, Any]:
        """Solo es invocado en estado borrador."""
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_borrador_o_error(
            formulario,
            "No se puede prellenar un formulario que ya fue enviado",
        )
        documentos = self._documentos.listar_documentos(formulario_id)
        return await self._analisis.prellenar_multiples_documentos(documentos)

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _buscar_formulario_o_error(self, formulario_id: str) -> Formulario:
        """Variante de dominio (sin HTTPException). Usada por el flujo /enviar."""
        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    @staticmethod
    def _verificar_estado_borrador_o_error(formulario: Formulario, mensaje_error: str) -> None:
        """Variante de dominio (sin HTTPException). Usada por el flujo /enviar."""
        if not es_estado_borrador(formulario.estado):
            raise FormularioNoEditableError(mensaje_error)
