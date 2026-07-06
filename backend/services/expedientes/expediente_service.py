"""
ExpedienteService — gestión de formularios enviados para el portal interno.

Responsabilidades:
  - Listar formularios en estado no-borrador (enviados, validados, rechazados).
  - Recuperar el detalle completo de un expediente con documentos y validaciones.
  - Resolver la ruta de un documento en disco para descarga directa.
  - Aprobar o rechazar un formulario enviado (cambio de estado manual).
"""

import json
from typing import Any, Dict, List, Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.constantes import (
    CAUSAL_CIERRE_INFORME_FINAL,
    CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
    CAUSAL_CIERRE_RECHAZADO_CON_INFORME_FINAL,
    CAUSALES_CIERRE_EXPEDIENTE,
    MODO_TRABAJO_ACTUALIZACION_REABIERTA,
    MODO_TRABAJO_CORRECCION,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
    TIPO_DOCUMENTO_REPORTE_FINAL,
)
from domain.excepciones import (
    DocumentoNoEncontradoError,
    FormularioNoEncontradoError,
    FormularioNoEditableError,
    SinPermisoError,
)
from domain.formulario.entidades import FormularioDominio
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import RepositorioExpediente
from domain.formulario.tipos import EstadoFormulario, TipoSolicitud
from services.acceso_manual.acceso_manual_service import AccesoManualService
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
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        acceso_service: Optional[AccesoManualService] = None,
        email_service: Optional[INotificador] = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._carga_handler = carga_handler
        self._comparador = comparador
        self._aprobacion_rechazo = aprobacion_rechazo_handler
        self._devolucion = devolucion_handler
        self._auditoria = repo_auditoria
        self._acceso_service = acceso_service
        self._email_service = email_service

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
            "tipo_solicitud":        formulario.tipo_solicitud,
            "estado":                formulario.estado,
            "modo_trabajo":          self._resolver_modo_trabajo(formulario),
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
        causal_cierre = self._obtener_causal_cierre(formulario_id) if formulario.estado == EstadoFormulario.CERRADO.value else None
        return {
            "formulario_id":     formulario.id,
            "codigo_peticion":   formulario.codigo_peticion,
            "razon_social":      formulario.razon_social,
            "tipo_contraparte":  formulario.tipo_contraparte,
            "tipo_persona":      formulario.tipo_persona,
            "tipo_solicitud":    formulario.tipo_solicitud,
            "estado":            formulario.estado,
            "modo_trabajo":      self._resolver_modo_trabajo(formulario),
            "numero_correccion": formulario.numero_correccion or 0,
            "campos_a_corregir": formulario.campos_a_corregir,
            "causal_cierre":     causal_cierre,
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
        causal_cierre: str = CAUSAL_CIERRE_INFORME_FINAL,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        self._validar_causal_cierre(causal_cierre)
        resultado = self._carga_handler.ejecutar(ComandoCargaDocumento(
            formulario_id=formulario_id,
            archivo_bytes=archivo_bytes,
            nombre_archivo=nombre_archivo,
            content_type=content_type,
            justificacion=justificacion,
            actor_id=actor_id,
            tipo_documento=TIPO_DOCUMENTO_REPORTE_FINAL,
            causal_cierre=causal_cierre,
            contrapartes_permitidas=contrapartes_permitidas,
        ))
        return {
            **resultado,
            "causal_cierre": causal_cierre,
            "reporte_final_cargado": True,
        }

    def cerrar_sin_reporte_final(
        self,
        formulario_id: str,
        justificacion: str,
        actor_id: str,
        causal_cierre: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        self._validar_causal_cierre(causal_cierre)
        if causal_cierre != CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS:
            raise ValueError("El informe final en PDF es obligatorio para esta causal de cierre.")

        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.cerrar_con_reporte()

        self._registrar_evento_ciclo_vida(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.EXPEDIENTE_CERRADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            metadata={
                "causal_cierre": causal_cierre,
                "requiere_reporte_final": False,
                "justificacion": justificacion.strip(),
            },
        )
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)
        return {
            "estado": dominio.estado.value,
            "causal_cierre": causal_cierre,
            "reporte_final_cargado": False,
        }

    def reabrir_por_actualizacion(
        self,
        formulario_id: str,
        justificacion: str,
        actor_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        if formulario.tipo_solicitud != TipoSolicitud.ACTUALIZACION.value:
            raise FormularioNoEditableError(
                "Solo los expedientes de actualización pueden reabrirse para continuar el proceso."
            )

        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.reabrir_por_actualizacion()
        campos_reapertura = self._construir_campos_reapertura_actualizacion(justificacion)
        datos_acceso = (
            self._acceso_service.reactivar_acceso_para_trabajo_expediente(formulario_id)
            if self._acceso_service
            else None
        )

        self._registrar_evento_ciclo_vida(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.EXPEDIENTE_REABIERTO_ACTUALIZACION,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            metadata={"justificacion": justificacion.strip()},
        )
        self._repo.actualizar_para_reapertura_actualizacion(
            formulario_id,
            dominio.estado.value,
            campos_reapertura,
        )

        correo_notificado = datos_acceso.get("correo_destinatario") if datos_acceso else None
        enlace_acceso = datos_acceso.get("enlace_diligenciamiento") if datos_acceso else None
        correo_enviado = False
        if self._email_service and correo_notificado:
            correo_enviado = self._email_service.enviar_notificacion_actualizacion_reabierta(
                correo_destinatario=correo_notificado,
                observaciones=justificacion.strip(),
                enlace_diligenciamiento=enlace_acceso,
            )

        return {
            "estado": dominio.estado.value,
            "modo_trabajo": MODO_TRABAJO_ACTUALIZACION_REABIERTA,
            "correo_notificado": correo_notificado,
            "correo_enviado": correo_enviado,
        }

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

    def _obtener_causal_cierre(self, formulario_id: str) -> Optional[str]:
        """Obtiene la causal de cierre desde el evento de auditoría más reciente."""
        if not self._auditoria:
            return None
        eventos = self._auditoria.listar_eventos(formulario_id)
        if not eventos:
            return None
        for evento in reversed(eventos):
            if evento.tipo_evento == TipoEvento.EXPEDIENTE_CERRADO:
                metadata = evento.metadata or {}
                return metadata.get("causal_cierre")
        return None

    def _validar_causal_cierre(self, causal_cierre: str) -> None:
        if causal_cierre not in CAUSALES_CIERRE_EXPEDIENTE:
            raise ValueError("La causal de cierre no es válida.")

    def _registrar_evento_ciclo_vida(
        self,
        formulario_id: str,
        tipo_evento: str,
        estado_anterior: str,
        estado_nuevo: str,
        actor_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._auditoria:
            return
        self._auditoria.registrar_evento(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=tipo_evento,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata=metadata,
        ))

    @staticmethod
    def _construir_campos_reapertura_actualizacion(justificacion: str) -> str:
        return json.dumps({
            "tipo": MODO_TRABAJO_ACTUALIZACION_REABIERTA,
            "especificaciones": justificacion.strip(),
            "campos": [],
        }, ensure_ascii=False)

    @staticmethod
    def _resolver_modo_trabajo(formulario) -> str:
        if formulario.estado != EstadoFormulario.EN_CORRECCION.value:
            return ""
        raw = getattr(formulario, "campos_a_corregir", None)
        if raw:
            try:
                datos = json.loads(raw)
                if datos.get("tipo") == MODO_TRABAJO_ACTUALIZACION_REABIERTA:
                    return MODO_TRABAJO_ACTUALIZACION_REABIERTA
            except (TypeError, ValueError):
                pass
        return MODO_TRABAJO_CORRECCION
