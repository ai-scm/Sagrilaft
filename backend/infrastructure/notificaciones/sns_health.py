"""
Health check de SNS — valida credenciales y conectividad al arranque.

Permite detectar problemas de configuración antes de que llegue tráfico real.

Comportamiento según entorno (APP_ENV):
  - development : publica un mensaje de prueba real (verifica sns:Publish end-to-end)
  - production  : solo consulta atributos del topic (sns:GetTopicAttributes), sin spam
"""

import logging
from typing import Optional

from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config

from infrastructure.configuracion import AWSConfig, SnsConfig

logger = logging.getLogger(__name__)

# Timeouts agresivos: queremos fallar rápido al arranque si AWS no responde
_CONFIG_BOTO = Config(
    connect_timeout=3,
    read_timeout=5,
    retries={"max_attempts": 2, "mode": "standard"},
)


def validar_sns_al_arranque(
    sns_config: SnsConfig,
    aws_config: AWSConfig,
    entorno: str = "development",
) -> Optional[str]:
    """
    Verifica que las credenciales AWS y el topic SNS sean accesibles.

    Args:
        sns_config: Configuración del topic SNS.
        aws_config: Credenciales y región AWS.
        entorno:    "development" publica un mensaje de prueba real;
                    "production" solo consulta atributos (sin enviar emails).

    Returns:
        None si todo está OK, mensaje de error descriptivo si falla.
    """
    if not sns_config.configurado:
        return None  # SNS deshabilitado — no es un error

    import boto3

    try:
        cliente = boto3.client(
            "sns",
            region_name=aws_config.region,
            aws_access_key_id=aws_config.access_key_id or None,
            aws_secret_access_key=aws_config.secret_access_key or None,
            config=_CONFIG_BOTO,
        )

        if entorno == "development":
            _verificar_publicando(cliente, sns_config.topic_arn)
        else:
            _verificar_con_atributos(cliente, sns_config.topic_arn)

        logger.info(
            "✓ SNS health check OK [%s] — topic accesible: %s",
            entorno, sns_config.topic_arn,
        )
        return None

    except ClientError as e:
        codigo = e.response.get("Error", {}).get("Code", "Unknown")
        if codigo in ("NotFound", "KMSDisabled"):
            return f"Topic SNS no existe: {sns_config.topic_arn}"
        elif codigo in ("AuthorizationError", "AccessDenied"):
            return f"Sin permisos para acceder al topic SNS: {sns_config.topic_arn}"
        else:
            return f"Error SNS ({codigo}): {e}"

    except BotoCoreError as e:
        return f"Error conectando con AWS SNS: {e}"

    except Exception as e:
        return f"Error inesperado validando SNS: {e}"


# ── Estrategias de verificación ───────────────────────────────────────────────

def _verificar_publicando(cliente, topic_arn: str) -> None:
    """Desarrollo: publica un mensaje real para verificar sns:Publish end-to-end."""
    cliente.publish(
        TopicArn=topic_arn,
        Subject="[SAGRILAFT] Health check — desarrollo",
        Message="Verificación de conectividad al arranque del servidor (solo desarrollo).",
    )


def _verificar_con_atributos(cliente, topic_arn: str) -> None:
    """Producción: consulta atributos del topic sin enviar mensajes al equipo."""
    cliente.get_topic_attributes(TopicArn=topic_arn)
