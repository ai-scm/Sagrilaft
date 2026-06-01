"""
Puerto de notificaciones transaccionales.

INotificador: contrato para el envío de avisos al usuario final.

DIP: los servicios de aplicación dependen de este protocolo,
no de EmailService ni del transporte SMTP concreto.
OCP: cambiar de SMTP a SendGrid/SES/SMS solo requiere implementar este Protocol.
"""

from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class INotificador(Protocol):
    """Puerto para envío de notificaciones transaccionales al usuario final."""

    def enviar_notificacion_devolucion(
        self,
        correo_destinatario: str,
        especificaciones_correccion: str,
        enlace_diligenciamiento: Optional[str] = None,
        campos_identificados: Optional[List[str]] = None,
    ) -> bool:
        """
        Notifica al destinatario que debe corregir su formulario SAGRILAFT.

        Returns True si la notificación se entregó; False si no se pudo enviar.
        """
        ...

    def enviar_notificacion_rechazo(
        self,
        correo_destinatario: str,
        mensaje_para_destinatario: str,
    ) -> bool:
        """
        Notifica al destinatario que su formulario fue rechazado.

        El mensaje es redactado por el operador y no expone el motivo interno
        de compliance. Returns True si la notificación se entregó.
        """
        ...
