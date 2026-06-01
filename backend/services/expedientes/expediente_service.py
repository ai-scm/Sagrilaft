"""
ExpedienteService — gestión de formularios enviados para el portal interno.

Responsabilidades:
  - Listar formularios en estado no-borrador (enviados, validados, rechazados).
  - Recuperar el detalle completo de un expediente con documentos y validaciones.
  - Resolver la ruta de un documento en disco para descarga directa.
  - Aprobar o rechazar un formulario enviado (cambio de estado manual).
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.excepciones import DocumentoNoEncontradoError, FormularioNoEditableError, FormularioNoEncontradoError, SinPermisoError
from domain.formulario.entidades import FormularioDominio
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import RepositorioExpediente
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga

if TYPE_CHECKING:
    from services.acceso_manual.acceso_manual_service import AccesoManualService  # noqa: F401


_ESTADOS_EXPEDIENTE = [
    EstadoFormulario.ENVIADO,
    EstadoFormulario.EN_CORRECCION,
    EstadoFormulario.VALIDADO,
    EstadoFormulario.RECHAZADO,
    EstadoFormulario.PENDIENTE_FIRMA,
    EstadoFormulario.FIRMADO,
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
        repo_auditoria: Optional[RepositorioAuditoria] = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._auditoria = repo_auditoria

    def _registrar(self, evento: EventoAuditoria) -> None:
        """Registra un evento de auditoría si el repositorio está disponible."""
        if self._auditoria:
            self._auditoria.registrar_evento(evento)

    # ─── Queries internas ─────────────────────────────────────────────────────

    def _buscar_formulario_expediente(self, formulario_id: str, contrapartes_permitidas: Optional[List[str]] = None):
        formulario = self._repo.obtener(formulario_id, _ESTADOS_EXPEDIENTE)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)
        return formulario

    def _buscar_documento_descargable(self, formulario_id: str, doc_id: str):
        """
        Retorna el documento si y solo si pertenece a un expediente (no borrador).

        Regla de negocio: para descargar desde el portal interno, el formulario
        ya debió haber sido enviado (o estar en estados posteriores como validado/rechazado).
        """
        return self._repo.buscar_documento_descargable(
            formulario_id, doc_id, _ESTADOS_EXPEDIENTE
        )

    def _conteos_documentos_por_formulario(self, ids_formularios: list[str]) -> dict[str, int]:
        """Cuenta documentos activos en una sola query GROUP BY — evita N+1.

        Excluye el certificado SAGRILAFT porque es un artefacto de firma generado
        automáticamente, no un documento subido por el usuario. El contador debe
        coincidir con lo que el operador ve en el detalle del expediente.
        """
        return self._repo.contar_documentos(ids_formularios)

    # ─── Serialización ────────────────────────────────────────────────────────

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

    def obtener_expediente(self, formulario_id: str, contrapartes_permitidas: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Recupera los metadatos del expediente y sus documentos adjuntos.

        Devuelve únicamente los campos que el portal necesita para la vista de detalle.
        Los datos del formulario (financieros, tributarios, etc.) no se exponen aquí —
        están disponibles exclusivamente en el PDF descargable.

        Lanza FormularioNoEncontradoError si el formulario no existe o está en borrador.
        """
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documentos = self._repo.listar_documentos(formulario_id)

        return {
            "formulario_id":    formulario.id,
            "codigo_peticion":  formulario.codigo_peticion,
            "razon_social":     formulario.razon_social,
            "tipo_contraparte": formulario.tipo_contraparte,
            "estado":              formulario.estado,
            "numero_correccion":   formulario.numero_correccion or 0,
            "updated_at":          formulario.updated_at,
            "documentos": [
                {
                    "id":             doc.id,
                    "tipo_documento": doc.tipo_documento,
                    "nombre_archivo": doc.nombre_archivo,
                    "tamano":         doc.tamano,
                    "version_numero": doc.version_numero,
                    "created_at":     doc.created_at,
                }
                for doc in documentos
            ],
        }

    # ─── Aprobación / Rechazo ─────────────────────────────────────────────────

    def aprobar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.aprobar()  # ENVIADO → VALIDADO; lanza FormularioNoEditableError si no aplica
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_APROBADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
        ))
        return {"estado": dominio.estado.value}

    def rechazar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
        motivo: str = "",
        mensaje_para_destinatario: Optional[str] = None,
        acceso_service: Optional["AccesoManualService"] = None,
        email_service: Optional[INotificador] = None,
    ) -> Dict[str, Any]:
        """
        Rechaza el formulario de forma definitiva y registra el motivo en auditoría.

        Si el operador redactó un mensaje_para_destinatario y los servicios de
        acceso y email están disponibles, notifica al destinatario por correo.
        El motivo interno nunca se expone al destinatario.
        """
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.rechazar()  # ENVIADO|VALIDADO → RECHAZADO; lanza FormularioNoEditableError si no aplica
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_RECHAZADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={"motivo": motivo},
        ))

        notificacion_enviada = self._notificar_rechazo_si_aplica(
            formulario_id=formulario_id,
            mensaje_para_destinatario=mensaje_para_destinatario,
            acceso_service=acceso_service,
            email_service=email_service,
        )

        return {
            "estado":               dominio.estado.value,
            "motivo":               motivo,
            "notificacion_enviada": notificacion_enviada,
        }

    def _notificar_rechazo_si_aplica(
        self,
        formulario_id: str,
        mensaje_para_destinatario: Optional[str],
        acceso_service: Optional["AccesoManualService"],
        email_service: Optional[INotificador],
    ) -> bool:
        """
        Envía la notificación de rechazo al destinatario si el operador la redactó.

        Retorna False si no hay mensaje, no hay servicios disponibles, o el
        formulario no tiene destinatario registrado.
        """
        if not mensaje_para_destinatario:
            return False
        if not acceso_service or not email_service:
            return False

        correo_destinatario = acceso_service.obtener_correo_destinatario(formulario_id)
        if not correo_destinatario:
            return False

        return email_service.enviar_notificacion_rechazo(
            correo_destinatario=correo_destinatario,
            mensaje_para_destinatario=mensaje_para_destinatario,
        )

    def devolver_para_correccion(
        self,
        formulario_id: str,
        especificaciones: str,
        campos_identificados: List[str],
        acceso_service: "AccesoManualService",
        email_service: Optional[INotificador] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Devuelve el formulario al remitente para que corrija la información indicada.

        Transiciones permitidas: ENVIADO → EN_CORRECCION, VALIDADO → EN_CORRECCION.
        Reactiva el acceso manual vinculado y notifica al destinatario por correo.

        Los campos_identificados se persisten como JSON junto con las especificaciones,
        permitiendo que el formulario destaque visualmente los campos que requieren atención.
        """
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.devolver_para_correccion()  # ENVIADO|VALIDADO → EN_CORRECCION, incrementa numero_correccion

        campos_a_corregir_json = json.dumps(
            {"especificaciones": especificaciones, "campos": campos_identificados},
            ensure_ascii=False,
        )

        # Modifica AccesoManual en la sesión sin commit (el commit lo hace actualizar_para_correccion)
        datos_acceso = acceso_service.reactivar_acceso_para_correccion(formulario_id)
        self._repo.actualizar_para_correccion(
            formulario_id,
            dominio.estado.value,
            dominio.numero_correccion,
            campos_a_corregir_json,
        )

        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_DEVUELTO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={
                "numero_correccion": dominio.numero_correccion,
                "especificaciones":  especificaciones,
                "campos":            campos_identificados,
            },
        ))

        correo_notificado = datos_acceso["correo_destinatario"] if datos_acceso else None
        enlace_acceso     = datos_acceso["enlace_diligenciamiento"] if datos_acceso else None

        correo_enviado = False
        if email_service and correo_notificado:
            correo_enviado = email_service.enviar_notificacion_devolucion(
                correo_destinatario=correo_notificado,
                especificaciones_correccion=especificaciones,
                enlace_diligenciamiento=enlace_acceso,
                campos_identificados=campos_identificados or None,
            )

        return {
            "estado":            dominio.estado.value,
            "correo_notificado": correo_notificado,
            "correo_enviado":    correo_enviado,
        }

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def resolver_documento_para_descarga(
        self, formulario_id: str, doc_id: str, contrapartes_permitidas: Optional[List[str]] = None
    ) -> InfoDescarga:
        """
        Verifica que el documento pertenece al expediente y devuelve su info de descarga.

        El caller decide el tipo de respuesta según InfoDescarga.es_url.
        Lanza DocumentoNoEncontradoError si el documento no existe o fue eliminado.
        """
        self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documento = self._buscar_documento_descargable(formulario_id, doc_id)
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)

        if not self._storage.existe(documento.ruta_archivo):
            raise DocumentoNoEncontradoError(formulario_id, doc_id)

        content_type = documento.content_type or "application/octet-stream"
        return self._storage.info_descarga(documento.ruta_archivo, documento.nombre_archivo, content_type)
