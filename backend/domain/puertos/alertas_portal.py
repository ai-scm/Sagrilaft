"""
Puerto de alertas al portal interno.

IAlertasPortal: contrato para notificar al equipo interno sobre eventos
críticos del ciclo de vida de los formularios SAGRILAFT.

DIP: los servicios dependen de este protocolo, no de boto3 ni de SNS.
OCP: cambiar el canal (SNS → SES, Slack, etc.) solo requiere un nuevo adaptador.
"""

from enum import Enum
from typing import Optional, Protocol, runtime_checkable


class TipoAlerta(str, Enum):
    """Eventos del ciclo de vida que generan alertas al portal interno."""
    FORMULARIO_RECIBIDO  = "FORMULARIO_RECIBIDO"
    FORMULARIO_DEVUELTO  = "FORMULARIO_DEVUELTO"
    FORMULARIO_CORREGIDO = "FORMULARIO_CORREGIDO"
    FORMULARIO_ENVIADO_A_FIRMA = "FORMULARIO_ENVIADO_A_FIRMA"
    FORMULARIO_FIRMADO   = "FORMULARIO_FIRMADO"


@runtime_checkable
class IAlertasPortal(Protocol):
    """Puerto para envío de alertas al equipo interno del portal."""

    def alertar(
        self,
        tipo: TipoAlerta,
        formulario_id: str,
        razon_social: str,
        tipo_contraparte: str,
        codigo_peticion: Optional[str] = None,
        detalle: Optional[str] = None,
    ) -> bool:
        """
        Envía una alerta al equipo responsable del portal.

        Returns True si la alerta se entregó; False si falló o no está configurada.
        No lanza excepciones — las alertas son fire-and-forget.
        """
        ...
