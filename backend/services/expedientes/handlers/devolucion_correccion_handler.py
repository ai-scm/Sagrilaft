from __future__ import annotations

"""
DevolucionCorreccionHandler — gestión de devoluciones para corrección.

Responsabilidades:
  - Ejecutar lógica de devolución para corrección (cambio de estado, auditoría).
  - Reactivar acceso de usuario para diligenciar correcciones.
  - Notificar al destinatario sobre campos a corregir.
  - Registrar especificaciones y campos identificados para corrección.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import json

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.catalogo_correcciones import resolver_etiquetas_campos_corregibles
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
class ComandoDevolucion:
    """Comando para devolver un expediente para corrección — solo datos, sin dependencias."""
    formulario_id: str
    especificaciones: str
    campos_identificados: List[str]
    actor_id: Optional[str] = None
    contrapartes_permitidas: Optional[List[str]] = None

@dataclass
class ComandoDeshacerDevolucion:
    """Comando para revertir una devolución para corrección."""
    formulario_id: str
    actor_id: Optional[str] = None
    contrapartes_permitidas: Optional[List[str]] = None


class DevolucionCorreccionHandler:
    """Maneja la transición de devolución para corrección."""

    def __init__(
        self,
        repo_expediente: RepositorioExpediente,
        acceso_service: AccesoManualService,
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        alertas_service: Optional[IAlertasPortal] = None,
        email_service: Optional[INotificador] = None,
    ):
        self._repo = repo_expediente
        self._acceso_service = acceso_service
        self._repo_auditoria = repo_auditoria
        self._alertas = alertas_service
        self._email_service = email_service

    def ejecutar_devolucion(self, comando: ComandoDevolucion) -> Dict[str, Any]:
        """
        Ejecuta la devolución de un expediente para corrección.
        
        Argumentos:
            comando: ComandoDevolucion con especificaciones y campos
            
        Retorna:
            Dict con {"estado": "EN_CORRECCION", "correo_notificado": ..., "correo_enviado": ...}
            
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
        dominio.devolver_para_correccion()

        # Preparar JSON de especificaciones
        campos_json = json.dumps(
            {
                "especificaciones": comando.especificaciones,
                "campos": comando.campos_identificados,
            },
            ensure_ascii=False,
        )

        # Reactivar acceso en servicio de manual
        datos_acceso = self._acceso_service.reactivar_acceso_para_correccion(
            comando.formulario_id
        )

        # Actualizar repositorio
        self._repo.actualizar_para_correccion(
            comando.formulario_id,
            dominio.estado.value,
            dominio.numero_correccion,
            campos_json,
        )

        # Registrar auditoría
        if self._repo_auditoria:
            self._repo_auditoria.registrar_evento(EventoAuditoria(
                formulario_id=comando.formulario_id,
                tipo_evento=TipoEvento.FORMULARIO_DEVUELTO,
                estado_anterior=estado_anterior,
                estado_nuevo=dominio.estado.value,
                actor_id=comando.actor_id,
                actor_tipo=ActorTipo.OPERADOR,
                metadata={
                    "numero_correccion": dominio.numero_correccion,
                    "especificaciones": comando.especificaciones,
                    "campos": comando.campos_identificados,
                },
            ))

        # Generar alerta con detalle de campos
        self._alertar_devolucion(formulario, dominio, comando)

        # Notificar por correo
        correo_notificado = datos_acceso.get("correo_destinatario") if datos_acceso else None
        enlace_acceso = datos_acceso.get("enlace_diligenciamiento") if datos_acceso else None
        correo_enviado = False

        if self._email_service and correo_notificado:
            correo_enviado = self._email_service.enviar_notificacion_devolucion(
                correo_destinatario=correo_notificado,
                especificaciones_correccion=comando.especificaciones,
                enlace_diligenciamiento=enlace_acceso,
                campos_identificados=comando.campos_identificados or None,
            )

        return {
            "estado": dominio.estado.value,
            "correo_notificado": correo_notificado,
            "correo_enviado": correo_enviado,
        }

    # ─── Privados ─────────────────────────────────────────────────────────────

    def ejecutar_deshacer_devolucion(self, comando: ComandoDeshacerDevolucion) -> Dict[str, Any]:
        """
        Revierte la devolución de un expediente para corrección.
        """
        formulario = self._buscar_formulario(
            comando.formulario_id,
            comando.contrapartes_permitidas,
        )
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.deshacer_devolucion()

        # Actualizar repositorio
        self._repo.actualizar_para_deshacer_devolucion(
            comando.formulario_id,
            dominio.estado.value,
            dominio.numero_correccion,
        )

        # Registrar auditoría
        if self._repo_auditoria:
            self._repo_auditoria.registrar_evento(EventoAuditoria(
                formulario_id=comando.formulario_id,
                tipo_evento=TipoEvento.FORMULARIO_DEVOLUCION_REVERTIDA,
                estado_anterior=estado_anterior,
                estado_nuevo=dominio.estado.value,
                actor_id=comando.actor_id,
                actor_tipo=ActorTipo.OPERADOR,
            ))

        return {
            "estado": dominio.estado.value,
        }

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

    def _alertar_devolucion(
        self,
        formulario: Any,
        dominio: FormularioDominio,
        comando: ComandoDevolucion,
    ) -> None:
        """Genera y envía alerta de devolución con detalle de campos."""
        if not self._alertas:
            return

        # Obtener etiquetas de campos
        etiquetas_campos = resolver_etiquetas_campos_corregibles(
            comando.campos_identificados or []
        )

        # Construir detalle
        detalle_alerta = f"Corrección #{dominio.numero_correccion}\n"
        if etiquetas_campos:
            detalle_alerta += "\nCampos que requieren corrección:\n"
            detalle_alerta += "\n".join(f"• {etiqueta}" for etiqueta in etiquetas_campos)

        self._alertas.alertar(
            TipoAlerta.FORMULARIO_DEVUELTO,
            formulario.id,
            formulario.razon_social or "",
            formulario.tipo_contraparte or "",
            formulario.codigo_peticion,
            detalle=detalle_alerta.strip(),
        )
