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
import re
from typing import Optional

from botocore.exceptions import ClientError

from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from infrastructure.configuracion import AWSConfig, SesConfig
from infrastructure.notificaciones.templates_correos import (
    construir_html_notificacion,
    construir_texto_plano_notificacion,
    obtener_asunto_correo,
)

logger = logging.getLogger(__name__)


def _parsear_destinatarios(valor: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[,;]", valor)
        if item.strip()
    ]


class SesAlertasPortal:
    """Adaptador de alertas que publica via Amazon SES.

    Envia emails multipart/alternative con HTML profesional y fallback plaintext.
    Las suscripciones de email reciben notificaciones con botón directo clickeable.
    """

    def __init__(
        self,
        ses_config: SesConfig,
        aws_config: AWSConfig,
        url_portal_interno: str,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._email_origen = ses_config.email_origen
        # Obligatorio: AppConfig.portal_interno_url es la única fuente de
        # verdad (ver infrastructure/configuracion.py) — este adaptador ya
        # no define su propio default.
        self._url_portal = url_portal_interno

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
            # Para alertas de devolución (acción 5 → trazabilidad interna del área),
            # omitir CTA (botón, enlace, acceso manual) ya que el área responsable
            # ya verificó y decidió devolver. El botón solo es necesario para
            # la contraparte (acción 4 → email_service).
            incluir_cta = tipo != TipoAlerta.FORMULARIO_DEVUELTO

            # Construir versiones HTML y texto plano
            cuerpo_html = construir_html_notificacion(
                tipo_alerta=tipo,
                formulario_id=formulario_id,
                razon_social=razon_social,
                tipo_contraparte=tipo_contraparte,
                codigo_peticion=codigo_peticion,
                url_portal=self._url_portal,
                detalle=detalle,
                incluir_cta=incluir_cta,
            )

            cuerpo_texto = construir_texto_plano_notificacion(
                tipo_alerta=tipo,
                formulario_id=formulario_id,
                razon_social=razon_social,
                tipo_contraparte=tipo_contraparte,
                codigo_peticion=codigo_peticion,
                url_portal=self._url_portal,
                detalle=detalle,
                incluir_cta=incluir_cta,
            )

            destinatarios = _parsear_destinatarios(
                os.getenv("ALERTAS_EMAIL_DESTINATARIO")
            )
            if not destinatarios:
                logger.warning("SES alertas sin destinatarios configurados")
                return False

            # Enviar via SES con estructura multipart/alternative
            respuesta = self._cliente.send_email(
                Source=self._email_origen,
                Destination={"ToAddresses": destinatarios},
                Message={
                    "Subject": {"Data": obtener_asunto_correo(tipo)},
                    "Body": {
                        "Html": {"Data": cuerpo_html, "Charset": "UTF-8"},
                        "Text": {"Data": cuerpo_texto, "Charset": "UTF-8"},
                    },
                },
            )

            self._enviadas += 1
            logger.info(
                f"Email enviado via SES: tipo={tipo.value}, "
                f"formulario={formulario_id}, destinatarios={len(destinatarios)}, "
                f"message_id={respuesta['MessageId']}"
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

    @property
    def estadisticas(self) -> dict:
        """Retorna contadores para observabilidad."""
        return {
            "enviadas": self._enviadas,
            "fallidas": self._fallidas,
            "total": self._enviadas + self._fallidas,
        }

    def metricas(self) -> dict:
        """Expone contadores en memoria para el endpoint /health."""
        return self.estadisticas
