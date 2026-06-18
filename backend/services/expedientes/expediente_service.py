"""
ExpedienteService — gestión de formularios enviados para el portal interno.

Responsabilidades:
  - Listar formularios en estado no-borrador (enviados, validados, rechazados).
  - Recuperar el detalle completo de un expediente con documentos y validaciones.
  - Resolver la ruta de un documento en disco para descarga directa.
  - Aprobar o rechazar un formulario enviado (cambio de estado manual).
"""

from typing import Any, Dict, List, Optional

from domain.excepciones import (
    DocumentoNoEncontradoError,
    FormularioNoEncontradoError,
    SinPermisoError,
)
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.repositorios import RepositorioExpediente
from domain.formulario.tipos import EstadoFormulario
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_REPORTE_FINAL
from services.expedientes.comparacion import ComparadorService
from services.expedientes.handlers import (
    AprobacionRechazoHandler,
    CargaDocumentoHandler,
    ComandoAprobacion,
    ComandoCargaDocumento,
    ComandoDevolucion,
    ComandoRechazo,
    DevolucionCorreccionHandler,
)

_ESTADOS_EXPEDIENTE = [
    EstadoFormulario.ENVIADO,
    EstadoFormulario.EN_CORRECCION,
    EstadoFormulario.VALIDADO,
    EstadoFormulario.RECHAZADO,
    EstadoFormulario.PENDIENTE_FIRMA,
    EstadoFormulario.FIRMADO,
    EstadoFormulario.CERRADO,
]


class ExpedienteService:
    """
    Servicio de gestión de expedientes para el portal interno.

    Responsabilidades:
      - Listar y detallar formularios en estado no-borrador.
      - Resolver documentos adjuntos para descarga directa.
      - Aprobar o rechazar un formulario enviado (transición de estado manual).
    """

    def __init__(
        self,
        repo: RepositorioExpediente,
        storage: IAlmacenamiento,
        carga_handler: CargaDocumentoHandler,
        comparador: ComparadorService,
        aprobacion_rechazo_handler: AprobacionRechazoHandler,
        devolucion_handler: DevolucionCorreccionHandler,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._carga_handler = carga_handler
        self._comparador = comparador
        self._aprobacion_rechazo = aprobacion_rechazo_handler
        self._devolucion = devolucion_handler

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _buscar_formulario_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ):
        formulario = self._repo.obtener(formulario_id, _ESTADOS_EXPEDIENTE)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)
        return formulario

    def _buscar_documento_descargable(self, formulario_id: str, doc_id: str):
        return self._repo.buscar_documento_descargable(
            formulario_id, doc_id, _ESTADOS_EXPEDIENTE
        )

    def _conteos_documentos_por_formulario(self, ids_formularios: list[str]) -> dict[str, int]:
        return self._repo.contar_documentos(ids_formularios)

    def _serializar_resumen(self, formulario, cantidad_documentos: int) -> Dict[str, Any]:
        return {
            "formulario_id":         formulario.id,
            "codigo_peticion":       formulario.codigo_peticion,
            "razon_social":          formulario.razon_social,
            "numero_identificacion": formulario.numero_identificacion,
            "tipo_contraparte":      formulario.tipo_contraparte,
            "tipo_persona":          formulario.tipo_persona,
            "estado":                formulario.estado,
            "numero_correccion":     formulario.numero_correccion or 0,
            "cantidad_documentos":   cantidad_documentos,
            "created_at":            formulario.created_at,
            "updated_at":            formulario.updated_at,
        }

    # ─── Listado ──────────────────────────────────────────────────────────────

    def listar_expedientes(
        self,
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        formularios = self._repo.listar(
            _ESTADOS_EXPEDIENTE, tipo_contraparte, busqueda, contrapartes_permitidas
        )
        conteos = self._conteos_documentos_por_formulario([f.id for f in formularios])
        return [self._serializar_resumen(f, conteos.get(f.id, 0)) for f in formularios]

    # ─── Detalle ──────────────────────────────────────────────────────────────

    def obtener_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documentos = self._repo.listar_documentos(formulario_id)
        return {
            "formulario_id":     formulario.id,
            "codigo_peticion":   formulario.codigo_peticion,
            "razon_social":      formulario.razon_social,
            "tipo_contraparte":  formulario.tipo_contraparte,
            "tipo_persona":      formulario.tipo_persona,
            "estado":            formulario.estado,
            "numero_correccion": formulario.numero_correccion or 0,
            "updated_at":        formulario.updated_at,
            "documentos": [
                {
                    "id":             doc.id,
                    "tipo_documento": doc.tipo_documento,
                    "nombre_archivo": doc.nombre_archivo,
                    "tamano":         doc.tamano,
                    "version_numero": doc.version_numero,
                    "version_anterior_id": doc.version_anterior_id,
                    "created_at":     doc.created_at,
                    "subido_por":     doc.subido_por,
                }
                for doc in documentos
            ],
        }

    def comparar_ultima_correccion(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._comparador.comparar_ultima_correccion(
            formulario_id,
            contrapartes_permitidas,
        )

    def generar_reporte_comparacion_pdf(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> bytes:
        return self._comparador.generar_reporte_comparacion_pdf(
            formulario_id,
            contrapartes_permitidas,
        )

    # ─── Carga Manual ─────────────────────────────────────────────────────────

    def cargar_formulario_manual(
        self,
        formulario_id: str,
        archivo_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
        justificacion: str,
        actor_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._carga_handler.ejecutar(ComandoCargaDocumento(
            formulario_id=formulario_id,
            archivo_bytes=archivo_bytes,
            nombre_archivo=nombre_archivo,
            content_type=content_type,
            justificacion=justificacion,
            actor_id=actor_id,
            tipo_documento=TIPO_DOCUMENTO_FORMULARIO_PDF,
            contrapartes_permitidas=contrapartes_permitidas,
        ))

    def cargar_reporte_final(
        self,
        formulario_id: str,
        archivo_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
        justificacion: str,
        actor_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._carga_handler.ejecutar(ComandoCargaDocumento(
            formulario_id=formulario_id,
            archivo_bytes=archivo_bytes,
            nombre_archivo=nombre_archivo,
            content_type=content_type,
            justificacion=justificacion,
            actor_id=actor_id,
            tipo_documento=TIPO_DOCUMENTO_REPORTE_FINAL,
            contrapartes_permitidas=contrapartes_permitidas,
        ))

    # ─── Aprobación / Rechazo ─────────────────────────────────────────────────

    def aprobar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._aprobacion_rechazo.ejecutar_aprobacion(ComandoAprobacion(
            formulario_id=formulario_id,
            actor_id=actor_id,
            contrapartes_permitidas=contrapartes_permitidas,
        ))

    def rechazar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
        motivo: str = "",
        mensaje_para_destinatario: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._aprobacion_rechazo.ejecutar_rechazo(ComandoRechazo(
            formulario_id=formulario_id,
            motivo=motivo,
            mensaje_para_destinatario=mensaje_para_destinatario,
            actor_id=actor_id,
            contrapartes_permitidas=contrapartes_permitidas,
        ))

    def devolver_para_correccion(
        self,
        formulario_id: str,
        especificaciones: str,
        campos_identificados: List[str],
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._devolucion.ejecutar_devolucion(ComandoDevolucion(
            formulario_id=formulario_id,
            especificaciones=especificaciones,
            campos_identificados=campos_identificados,
            actor_id=actor_id,
            contrapartes_permitidas=contrapartes_permitidas,
        ))

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def resolver_documento_para_descarga(
        self,
        formulario_id: str,
        doc_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> InfoDescarga:
        self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documento = self._buscar_documento_descargable(formulario_id, doc_id)
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        if not self._storage.existe(documento.ruta_archivo):
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        content_type = documento.content_type or "application/octet-stream"
        return self._storage.info_descarga(documento.ruta_archivo, documento.nombre_archivo, content_type)
