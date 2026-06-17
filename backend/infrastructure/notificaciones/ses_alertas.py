"""
Adaptador SES para alertas al portal interno.

Implementa IAlertasPortal publicando mensajes directamente via Amazon SES.
Ventaja sobre SNS: Control total sobre MIME headers → Content-Type: text/html

Emails multipart/alternative:
  - Parte HTML: Profesional, responsive, con botón
  - Parte plaintext: Fallback para clientes sin soporte HTML
"""

import logging
import os
from typing import Optional

from botocore.exceptions import ClientError

from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from infrastructure.configuracion import AWSConfig, SesConfig
from infrastructure.notificaciones.templates_correos import (
    TipoAlertaTemplate,
    construir_html_notificacion,
    construir_texto_plano_notificacion,
)

logger = logging.getLogger(__name__)

_ASUNTO_POR_TIPO: dict[TipoAlerta, str] = {
    TipoAlerta.FORMULARIO_RECIBIDO: "[SAGRILAFT] Nuevo formulario recibido",
    TipoAlerta.FORMULARIO_DEVUELTO: "[SAGRILAFT] Formulario devuelto para corrección",
    TipoAlerta.FORMULARIO_CORREGIDO: "[SAGRILAFT] Formulario corregido y reenviado",
    TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA: "[SAGRILAFT] Formulario enviado a firma electrónica",
    TipoAlerta.FORMULARIO_FIRMADO: "[SAGRILAFT] Formulario firmado electrónicamente",
}


class SesAlertasPortal:
    """Adaptador de alertas que publica via Amazon SES.

    Envia emails multipart/alternative con HTML profesional y fallback plaintext.
    Las suscripciones de email reciben notificaciones con botón directo clickeable.
    """

    def __init__(
        self,
        ses_config: SesConfig,
        aws_config: AWSConfig,
        url_portal_interno: Optional[str] = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._email_origen = ses_config.email_origen
        self._url_portal = url_portal_interno or os.getenv(
            "PORTAL_INTERNO_URL",
            "https://portal.sagrilaft.com"
        )

        config_boto = Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 3, "mode": "standard"},
        )

        self._region = aws_config.region

        self._cliente = boto3.client(
            "ses",
            region_name=self._region,
            aws_access_key_id=aws_config.access_key_id or None,
            aws_secret_access_key=aws_config.secret_access_key or None,
            config=config_boto,
        )

        # Contadores para observabilidad vía /health
        self._enviadas: int = 0
        self._fallidas: int = 0

        logger.info(
            f"Alertas SES habilitadas (origen={self._email_origen}, portal_url={self._url_portal})"
        )

    def alertar(
        self,
        tipo: TipoAlerta,
        formulario_id: str,
        razon_social: str,
        tipo_contraparte: str,
        codigo_peticion: Optional[str] = None,
        detalle: Optional[str] = None,
    ) -> bool:
        """Envía notificación via SES directamente.

        Args:
            tipo: Tipo de evento (FORMULARIO_RECIBIDO, etc.)
            formulario_id: UUID del formulario
            razon_social: Nombre legal de la contraparte
            tipo_contraparte: 'cliente' o 'proveedor'
            codigo_peticion: Código único SAG-XXXXXXXX
            detalle: Información adicional opcional

        Returns:
            True si se envió exitosamente, False si falló.
        """
        try:
            # Mapear TipoAlerta (dominio) a TipoAlertaTemplate (templates)
            tipo_template = self._mapear_tipo_alerta(tipo)

            # Construir versiones HTML y texto plano
            cuerpo_html = construir_html_notificacion(
                tipo_alerta=tipo_template,
                formulario_id=formulario_id,
                razon_social=razon_social,
                tipo_contraparte=tipo_contraparte,
                codigo_peticion=codigo_peticion,
                url_portal=self._url_portal,
                detalle=detalle,
            )

            cuerpo_texto = construir_texto_plano_notificacion(
                tipo_alerta=tipo_template,
                formulario_id=formulario_id,
                razon_social=razon_social,
                tipo_contraparte=tipo_contraparte,
                codigo_peticion=codigo_peticion,
                url_portal=self._url_portal,
                detalle=detalle,
            )

            # Obtener email destinatario (placeholder, se reemplaza en real)
            # En producción, esto vendría de un parámetro adicional
            email_destinatario = os.getenv("ALERTAS_EMAIL_DESTINATARIO", "alerts@sagrilaft.com")

            # Enviar via SES con estructura multipart/alternative
            respuesta = self._cliente.send_email(
                Source=self._email_origen,
                Destination={"ToAddresses": [email_destinatario]},
                Message={
                    "Subject": {"Data": _ASUNTO_POR_TIPO[tipo]},
                    "Body": {
                        "Html": {"Data": cuerpo_html, "Charset": "UTF-8"},
                        "Text": {"Data": cuerpo_texto, "Charset": "UTF-8"},
                    },
                },
            )

            self._enviadas += 1
            logger.info(
                f"Email enviado via SES: tipo={tipo.value}, "
                f"formulario={formulario_id}, message_id={respuesta['MessageId']}"
            )
            return True

        except ClientError as e:
            self._fallidas += 1
            logger.error(
                f"Error enviando email SES: {e.response['Error']['Code']} - "
                f"{e.response['Error']['Message']}"
            )
            return False

        except Exception as e:
            self._fallidas += 1
            logger.error(f"Error inesperado enviando email: {e}", exc_info=True)
            return False

    def _mapear_tipo_alerta(self, tipo: TipoAlerta) -> TipoAlertaTemplate:
        """Convierte TipoAlerta (dominio) a TipoAlertaTemplate (templates)."""
        mapeo = {
            TipoAlerta.FORMULARIO_RECIBIDO: TipoAlertaTemplate.FORMULARIO_RECIBIDO,
            TipoAlerta.FORMULARIO_DEVUELTO: TipoAlertaTemplate.FORMULARIO_DEVUELTO,
            TipoAlerta.FORMULARIO_CORREGIDO: TipoAlertaTemplate.FORMULARIO_CORREGIDO,
            TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA: TipoAlertaTemplate.FORMULARIO_ENVIADO_A_FIRMA,
            TipoAlerta.FORMULARIO_FIRMADO: TipoAlertaTemplate.FORMULARIO_FIRMADO,
        }
        return mapeo[tipo]

    @property
    def estadisticas(self) -> dict:
        """Retorna contadores para observabilidad."""
        return {
            "enviadas": self._enviadas,
            "fallidas": self._fallidas,
            "total": self._enviadas + self._fallidas,
        }
