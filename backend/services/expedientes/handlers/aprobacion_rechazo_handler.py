from __future__ import annotations

"""
AprobacionRechazoHandler — gestión de aprobaciones y rechazos de expedientes.

Responsabilidades:
  - Ejecutar lógica de aprobación (cambio de estado, auditoría).
  - Ejecutar lógica de rechazo (cambio de estado, auditoría, notificaciones).
  - Manejar transiciones de estado a través del dominio.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.excepciones import FormularioNoEncontradoError, SinPermisoError
from domain.formulario.entidades import FormularioDominio
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import RepositorioExpediente

if TYPE_CHECKING:
    from services.acceso_manual.acceso_manual_service import AccesoManualService


_ESTADOS_EXPEDIENTE = [
    EstadoFormulario.ENVIADO,
    EstadoFormulario.EN_CORRECCION,
    EstadoFormulario.VALIDADO,
    EstadoFormulario.RECHAZADO,
    EstadoFormulario.PENDIENTE_FIRMA,
    EstadoFormulario.FIRMADO,
    EstadoFormulario.CERRADO,
]


@dataclass
class ComandoAprobacion:
    """Comando para aprobar un expediente."""
    formulario_id: str
    actor_id: Optional[str] = None
    contrapartes_permitidas: Optional[List[str]] = None


@dataclass
class ComandoRechazo:
    """Comando para rechazar un expediente — solo datos, sin dependencias."""
    formulario_id: str
    motivo: str = ""
    mensaje_para_destinatario: Optional[str] = None
    actor_id: Optional[str] = None
    contrapartes_permitidas: Optional[List[str]] = None


class AprobacionRechazoHandler:
    """Maneja las transiciones de estado: aprobación y rechazo."""

    def __init__(
        self,
        repo_expediente: RepositorioExpediente,
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        acceso_service: Optional[AccesoManualService] = None,
        email_service: Optional[INotificador] = None,
        alertas_service: Optional[IAlertasPortal] = None,
    ):
        self._repo = repo_expediente
        self._repo_auditoria = repo_auditoria
        self._acceso_service = acceso_service
        self._email_service = email_service
        self._alertas = alertas_service

    def ejecutar_aprobacion(self, comando: ComandoAprobacion) -> Dict[str, Any]:
        """
        Ejecuta la aprobación de un expediente.
        
        Argumentos:
            comando: ComandoAprobacion con formulario_id y actor_id
            
        Retorna:
            Dict con {"estado": "APROBADO"}
            
        Lanza:
            FormularioNoEncontradoError: Si el formulario no existe
            SinPermisoError: Si las contrapartes no coinciden
        """
        formulario = self._buscar_formulario(
            comando.formulario_id,
            comando.contrapartes_permitidas,
        )
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.aprobar()
        
        self._repo.actualizar_estado(comando.formulario_id, dominio.estado.value)
        
        if self._repo_auditoria:
            self._repo_auditoria.registrar_evento(EventoAuditoria(
                formulario_id=comando.formulario_id,
                tipo_evento=TipoEvento.FORMULARIO_APROBADO,
                estado_anterior=estado_anterior,
                estado_nuevo=dominio.estado.value,
                actor_id=comando.actor_id,
                actor_tipo=ActorTipo.OPERADOR,
            ))
        
        return {"estado": dominio.estado.value}

    def ejecutar_rechazo(self, comando: ComandoRechazo) -> Dict[str, Any]:
        """
        Ejecuta el rechazo de un expediente.
        
        Argumentos:
            comando: ComandoRechazo con datos de rechazo y notificación
            
        Retorna:
            Dict con {"estado": "RECHAZADO", "motivo": ..., "notificacion_enviada": ...}
            
        Lanza:
            FormularioNoEncontradoError: Si el formulario no existe
            SinPermisoError: Si las contrapartes no coinciden
        """
        formulario = self._buscar_formulario(
            comando.formulario_id,
            comando.contrapartes_permitidas,
        )
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.rechazar()
        
        self._repo.actualizar_estado(comando.formulario_id, dominio.estado.value)
        
        if self._repo_auditoria:
            self._repo_auditoria.registrar_evento(EventoAuditoria(
                formulario_id=comando.formulario_id,
                tipo_evento=TipoEvento.FORMULARIO_RECHAZADO,
                estado_anterior=estado_anterior,
                estado_nuevo=dominio.estado.value,
                actor_id=comando.actor_id,
                actor_tipo=ActorTipo.OPERADOR,
                metadata={"motivo": comando.motivo},
            ))
        
        self._alertar_rechazo(formulario, comando)
        notificacion_enviada = self._notificar_rechazo_si_aplica(comando)
        
        return {
            "estado": dominio.estado.value,
            "motivo": comando.motivo,
            "notificacion_enviada": notificacion_enviada,
        }

    # ─── Privados ─────────────────────────────────────────────────────────────

    def _buscar_formulario(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]],
    ) -> Any:
        """Busca un formulario en estado expediente validando contrapartes."""
        formulario = self._repo.obtener(formulario_id, _ESTADOS_EXPEDIENTE)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)
        return formulario

    def _notificar_rechazo_si_aplica(self, comando: ComandoRechazo) -> bool:
        """Notifica al destinatario sobre el rechazo si corresponde."""
        if not comando.mensaje_para_destinatario:
            return False
        if not self._acceso_service or not self._email_service:
            return False

        correo_destinatario = self._acceso_service.obtener_correo_destinatario(
            comando.formulario_id
        )
        if not correo_destinatario:
            return False

        return self._email_service.enviar_notificacion_rechazo(
            correo_destinatario=correo_destinatario,
            mensaje_para_destinatario=comando.mensaje_para_destinatario,
        )

    def _alertar_rechazo(self, formulario: Any, comando: ComandoRechazo) -> None:
        """Informa al area interna que el expediente fue rechazado."""
        if not self._alertas:
            return

        detalle_rechazo = f"Motivo interno: {comando.motivo.strip() or 'Sin motivo registrado'}"
        self._alertas.alertar(
            tipo=TipoAlerta.FORMULARIO_RECHAZADO,
            formulario_id=formulario.id,
            razon_social=formulario.razon_social or "",
            tipo_contraparte=formulario.tipo_contraparte or "",
            codigo_peticion=formulario.codigo_peticion,
            detalle=detalle_rechazo,
        )
