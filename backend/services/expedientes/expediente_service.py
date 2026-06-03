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
from domain.excepciones import (
    DocumentoNoEncontradoError,
    FormularioNoEncontradoError,
    SinPermisoError,
)
from domain.formulario.entidades import FormularioDominio
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import RepositorioExpediente
from domain.formulario.tipos import EstadoFormulario

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
        alertas_portal: Optional[IAlertasPortal] = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._auditoria = repo_auditoria
        self._alertas = alertas_portal

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _registrar(self, evento: EventoAuditoria) -> None:
        """Registra un evento de auditoría si el repositorio está disponible."""
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
        dominio.aprobar()
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
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.rechazar()
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
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.devolver_para_correccion()

        campos_json = json.dumps(
            {"especificaciones": especificaciones, "campos": campos_identificados},
            ensure_ascii=False,
        )
        datos_acceso = acceso_service.reactivar_acceso_para_correccion(formulario_id)
        self._repo.actualizar_para_correccion(
            formulario_id,
            dominio.estado.value,
            dominio.numero_correccion,
            campos_json,
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
        self._alertar(
            TipoAlerta.FORMULARIO_DEVUELTO,
            formulario,
            detalle=f"Corrección #{dominio.numero_correccion}",
        )

        correo_notificado = datos_acceso["correo_destinatario"] if datos_acceso else None
        enlace_acceso     = datos_acceso["enlace_diligenciamiento"] if datos_acceso else None
        correo_enviado    = False
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
