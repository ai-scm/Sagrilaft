"""
FormularioService — lógica de negocio para formularios SAGRILAFT.

Organiza responsabilidades en capas claras:
  - Funciones de serialización JSON: delegadas a serializacion.py
  - ValidadorEnvioFormulario: delegado a validacion_envio.py
  - DocumentoService: maneja CRUD y almacenamiento de adjuntos.
  - AnalisisDocumentosService: orquesta extracción de datos vía IA.
  - FormularioService: CRUD de formularios e integración (Facade).
"""

from typing import Any, Dict, List, Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.contratos import ExtractorIAImp, ResultadoEnvioFormulario
from domain.excepciones import (
    FormularioNoEditableError,
    FormularioNoEncontradoError,
)
from domain.formulario.entidades import FormularioDatos, FormularioDominio
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.repositorios import RepositorioDocumento, RepositorioFormulario
from domain.utils.estado_formulario import es_estado_editable
from services.formulario.almacenamiento_contraparte import resolver_key_contraparte
from services.formulario.analisis_service import (
    AnalisisDocumentosService,
    ResultadoGuardadoDocumento,
    obtener_config_analisis_por_defecto,
)
from services.formulario.documento_service import DocumentoService
from services.formulario.exportacion_pdf import ExportadorFormularioPdf
from services.formulario.serializacion import (
    construir_snapshot_formulario,
    formulario_a_dict,
    snapshot_version_formulario,
)
from services.formulario.validacion_envio import ValidadorEnvioFormulario


class FormularioService:
    """
    Servicio de negocio para la gestión de formularios SAGRILAFT.

    Actúa como Facade conectando el CRUD de formulario con la validación,
    los documentos y el análisis de IA.
    """

    def __init__(
        self,
        repo: RepositorioFormulario,
        repo_doc: RepositorioDocumento,
        extractor: ExtractorIAImp,
        storage: IAlmacenamiento,
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        alertas_portal: Optional[IAlertasPortal] = None,
    ) -> None:
        self._repo = repo
        self._validador_envio = ValidadorEnvioFormulario()
        self._documentos = DocumentoService(repo_doc, storage)
        self._exportador_pdf = ExportadorFormularioPdf()
        self._analisis = AnalisisDocumentosService(
            extractor,
            obtener_config_analisis_por_defecto(),
            storage,
        )
        self._auditoria = repo_auditoria
        self._alertas = alertas_portal

    def _registrar(self, evento: EventoAuditoria) -> None:
        if self._auditoria:
            self._auditoria.registrar_evento(evento)

    def _alertar(self, tipo: TipoAlerta, formulario, detalle: Optional[str] = None) -> None:
        """Dispara una alerta al portal si el adaptador está disponible."""
        if self._alertas:
            self._alertas.alertar(
                tipo=tipo,
                formulario_id=formulario.id,
                razon_social=formulario.razon_social or "",
                tipo_contraparte=formulario.tipo_contraparte or "",
                codigo_peticion=formulario.codigo_peticion,
                detalle=detalle,
            )

    # ─── CRUD de formulario ───────────────────────────────────────────────────

    def crear_borrador(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        formulario = self._repo.crear(datos)
        return formulario_a_dict(formulario)

    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        formulario = self._repo.obtener_por_codigo(codigo)
        if not formulario:
            raise FormularioNoEncontradoError(codigo)
        return construir_snapshot_formulario(formulario)

    def actualizar(self, formulario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_editable_o_error(
            formulario,
            "No se puede modificar un formulario que ya fue enviado",
        )
        formulario_actualizado = self._repo.actualizar(formulario_id, datos)
        return formulario_a_dict(formulario_actualizado)

    def enviar(self, formulario_id: str, actor_id: Optional[str] = None) -> ResultadoEnvioFormulario:
        formulario = self._buscar_formulario_o_error(formulario_id)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.enviar()  # valida BORRADOR|EN_CORRECCION → ENVIADO; lanza FormularioNoEditableError si no aplica

        errores = self._validador_envio.validar(formulario)
        if errores:
            return ResultadoEnvioFormulario(valido=False, errores=errores)

        prefijo = resolver_key_contraparte(formulario.tipo_contraparte, formulario.razon_social)
        self._documentos.mover_archivos_formulario_a_contraparte(formulario.id, prefijo)

        pdf_anterior = self._documentos.obtener_ultimo_formulario_pdf(formulario.id)
        numero_version_nuevo = (pdf_anterior.version_numero + 1) if pdf_anterior else 1

        nombre_pdf, pdf_bytes = self._exportador_pdf.generar_bytes_pdf(
            formulario, numero_version=numero_version_nuevo
        )
        key_pdf = f"{prefijo}/{nombre_pdf}"
        self._documentos.guardar_archivo(key_pdf, pdf_bytes, "application/pdf")
        self._documentos.registrar_documento_en_bd(
            formulario_id=formulario.id,
            tipo_documento=TIPO_DOCUMENTO_FORMULARIO_PDF,
            nombre_archivo=nombre_pdf,
            key=key_pdf,
            content_type="application/pdf",
            tamano=len(pdf_bytes),
            hash_sha256=self._documentos.calcular_hash(pdf_bytes),
            subido_por="SISTEMA",
            version_numero=numero_version_nuevo,
            version_anterior_id=pdf_anterior.id if pdf_anterior else None,
            snapshot_datos=snapshot_version_formulario(formulario),
        )

        self._repo.actualizar(formulario_id, {"estado": dominio.estado.value})
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_ENVIADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.CONTRAPARTE,
        ))

        # Alerta al portal: distingue envío inicial de corrección por el estado anterior
        tipo_alerta = (
            TipoAlerta.FORMULARIO_CORREGIDO
            if estado_anterior == EstadoFormulario.EN_CORRECCION.value
            else TipoAlerta.FORMULARIO_RECIBIDO
        )
        self._alertar(tipo_alerta, formulario)

        return ResultadoEnvioFormulario(valido=True, errores=[])

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
        self._verificar_estado_editable_o_error(
            formulario,
            "No se pueden agregar documentos a un formulario enviado",
        )

        key = self._documentos.key_borrador(formulario.codigo_peticion, nombre_archivo)
        self._documentos.guardar_archivo(key, contenido_bytes, content_type)

        from services.formulario.documento_service import _sanitizar_nombre_archivo
        nombre_seguro = _sanitizar_nombre_archivo(nombre_archivo)
        documento = self._documentos.registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_seguro,
            key=key,
            content_type=content_type,
            tamano=len(contenido_bytes),
            hash_sha256=self._documentos.calcular_hash(contenido_bytes),
        )
        return await self._analisis.analizar_nueva_carga(
            documento=documento,
            formulario=formulario,
        )

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_editable_o_error(
            formulario,
            "No se pueden eliminar documentos de un formulario enviado",
        )
        self._documentos.eliminar_documento(formulario_id, doc_id)

    def listar_documentos(self, formulario_id: str) -> List[Any]:
        self._buscar_formulario_o_error(formulario_id)
        return self._documentos.listar_documentos(formulario_id)

    def descargar_pdf_oficial(self, codigo_o_id: str) -> InfoDescarga:
        formulario = self._repo.obtener_por_codigo(codigo_o_id) or self._repo.obtener_por_id(codigo_o_id)
        if not formulario:
            raise FormularioNoEncontradoError(codigo_o_id)
            
        pdf = self._documentos.obtener_ultimo_formulario_pdf(formulario.id)
        if not pdf:
            from domain.excepciones import DocumentoNoEncontradoError
            raise DocumentoNoEncontradoError(codigo_o_id, "PDF_OFICIAL")
        return self._documentos.info_descarga(pdf)

    # ─── Pre-llenado con IA ───────────────────────────────────────────────────

    async def prellenar_documento(
        self, formulario_id: str, doc_id: str
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_editable_o_error(
            formulario,
            "No se puede prellenar un formulario que ya fue enviado",
        )
        documento = self._documentos.buscar_documento(formulario_id, doc_id)
        return await self._analisis.prellenar_documento(documento)

    async def prellenar_todos(self, formulario_id: str) -> Dict[str, Any]:
        formulario = self._buscar_formulario_o_error(formulario_id)
        self._verificar_estado_editable_o_error(
            formulario,
            "No se puede prellenar un formulario que ya fue enviado",
        )
        documentos = self._documentos.listar_documentos(formulario_id)
        return await self._analisis.prellenar_multiples_documentos(documentos)

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _buscar_formulario_o_error(self, formulario_id: str) -> FormularioDatos:
        formulario = self._repo.obtener_por_id(formulario_id)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    @staticmethod
    def _verificar_estado_editable_o_error(
        formulario: FormularioDatos, mensaje_error: str
    ) -> None:
        if not es_estado_editable(formulario.estado):
            raise FormularioNoEditableError(mensaje_error)
