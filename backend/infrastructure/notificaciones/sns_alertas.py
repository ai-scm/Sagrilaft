"""
Adaptador SNS para alertas al portal interno.

Implementa IAlertasPortal publicando mensajes en un topic de Amazon SNS.
Las suscripciones (email, SQS, Lambda) se gestionan fuera del código.

Prevención de duplicados: throttling temporal de 5 minutos por formulario+tipo.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from botocore.exceptions import ClientError

from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from infrastructure.configuracion import AWSConfig, SnsConfig
from infrastructure.notificaciones.templates_correos import (
    TipoAlertaTemplate,
    construir_html_notificacion,
    construir_texto_plano_notificacion,
)

logger = logging.getLogger(__name__)

# Ventana de throttling: no enviar la misma alerta si ya se envió en los últimos N minutos
THROTTLE_MINUTOS = 5

_ASUNTO_POR_TIPO: dict[TipoAlerta, str] = {
    TipoAlerta.FORMULARIO_RECIBIDO:  "[SAGRILAFT] Nuevo formulario recibido",
    TipoAlerta.FORMULARIO_DEVUELTO:  "[SAGRILAFT] Formulario devuelto para corrección",
    TipoAlerta.FORMULARIO_CORREGIDO: "[SAGRILAFT] Formulario corregido y reenviado",
    TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA: "[SAGRILAFT] Formulario enviado a firma electrónica",
    TipoAlerta.FORMULARIO_FIRMADO:   "[SAGRILAFT] Formulario firmado electrónicamente",
    TipoAlerta.FORMULARIO_RECHAZADO: "[SAGRILAFT] Formulario rechazado",
    TipoAlerta.REPORTE_FINAL_CARGADO: "[SAGRILAFT] Reporte final cargado",
}


class SnsAlertasPortal:
    """Adaptador de alertas que publica en Amazon SNS.
    
    Publica mensajes formatados con HTML y botón directo al formulario.
    Las suscripciones de email reciben notificaciones profesionales y accesibles.
    """

    def __init__(
        self,
        sns_config: SnsConfig,
        aws_config: AWSConfig,
        url_portal_interno: Optional[str] = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._topic_arn = sns_config.topic_arn
        # Usar parámetro, variable de entorno o valor por defecto para desarrollo
        self._url_portal = url_portal_interno or os.getenv(
            "PORTAL_INTERNO_URL",
            "https://portal.sagrilaft.com"
        )

        # Cache en memoria: clave = (formulario_id, tipo), valor = datetime del último envío.
        # Previene duplicados si el mismo evento se dispara varias veces en poco tiempo.
        self._ultimo_envio: dict[tuple[str, TipoAlerta], datetime] = {}

        # Contadores en memoria para observabilidad vía /health
        self._enviadas: int = 0
        self._fallidas: int = 0
        self._throttled: int = 0

        config_boto = Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 3, "mode": "standard"},
        )

        self._region = aws_config.region

        self._cliente = boto3.client(
            "sns",
            region_name=self._region,
            aws_access_key_id=aws_config.access_key_id or None,
            aws_secret_access_key=aws_config.secret_access_key or None,
            config=config_boto,
        )

        self._cloudwatch = boto3.client(
            "cloudwatch",
            region_name=self._region,
            aws_access_key_id=aws_config.access_key_id or None,
            aws_secret_access_key=aws_config.secret_access_key or None,
            config=config_boto,
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
        if self._esta_throttled(formulario_id, tipo):
            self._throttled += 1
            return True  # Silencio intencional — no es un error

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
            
            # Publicar con estructura JSON: email recibe HTML, otros canales reciben texto
            mensaje_json = json.dumps({
                "default": cuerpo_texto,
                "email": cuerpo_html,
            })
            
            respuesta = self._cliente.publish(
                TopicArn=self._topic_arn,
                Subject=_ASUNTO_POR_TIPO[tipo],
                Message=mensaje_json,
                MessageStructure="json",
                MessageAttributes={
                    "tipo_evento": {"DataType": "String", "StringValue": tipo.value}
                },
            )
            self._registrar_envio(formulario_id, tipo)
            self._enviadas += 1
            self._publicar_metrica("SNSAlertaEnviada", tipo)
            message_id = respuesta.get("MessageId", "unknown")
            logger.info(
                "sns_alerta_enviada tipo=%s formulario=%s message_id=%s",
                tipo.value, formulario_id, message_id,
            )
            return True
        except ClientError as e:
            self._fallidas += 1
            self._publicar_metrica("SNSAlertaFallida", tipo)
            codigo_error = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "sns_alerta_error tipo=%s formulario=%s error_code=%s error=%s",
                tipo.value, formulario_id, codigo_error, str(e),
            )
            return False
        except Exception:
            self._fallidas += 1
            self._publicar_metrica("SNSAlertaFallida", tipo)
            logger.exception(
                "sns_alerta_error_inesperado tipo=%s formulario=%s",
                tipo.value, formulario_id,
            )
            return False

    def metricas(self) -> dict:
        """Expone contadores en memoria para el endpoint /health."""
        return {
            "enviadas": self._enviadas,
            "fallidas": self._fallidas,
            "throttled": self._throttled,
        }

    def _publicar_metrica(self, nombre: str, tipo: TipoAlerta, valor: float = 1.0) -> None:
        """Publica una métrica custom en CloudWatch. Fire-and-forget: no bloquea ni lanza."""
        try:
            self._cloudwatch.put_metric_data(
                Namespace="SAGRILAFT",
                MetricData=[{
                    "MetricName": nombre,
                    "Value": valor,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "TipoAlerta", "Value": tipo.value}],
                }],
            )
        except Exception:
            # Métricas son best-effort — nunca deben interrumpir el flujo principal
            logger.debug("cloudwatch_metrica_fallida nombre=%s tipo=%s", nombre, tipo.value)

    # ── Throttling ────────────────────────────────────────────────────────────

    def _esta_throttled(self, formulario_id: str, tipo: TipoAlerta) -> bool:
        clave = (formulario_id, tipo)
        ultimo = self._ultimo_envio.get(clave)
        if ultimo is None:
            return False
        transcurrido = datetime.now(timezone.utc) - ultimo
        if transcurrido < timedelta(minutes=THROTTLE_MINUTOS):
            logger.warning(
                "sns_alerta_throttled tipo=%s formulario=%s último_envío_hace=%.1fs ventana=%dm",
                tipo.value, formulario_id, transcurrido.total_seconds(), THROTTLE_MINUTOS,
            )
            return True
        return False

    def _registrar_envio(self, formulario_id: str, tipo: TipoAlerta) -> None:
        self._ultimo_envio[(formulario_id, tipo)] = datetime.now(timezone.utc)
        self._limpiar_cache_viejo()


    def _limpiar_cache_viejo(self) -> None:
        """Elimina entradas expiradas del cache para evitar crecimiento ilimitado en memoria."""
        limite = datetime.now(timezone.utc) - timedelta(minutes=THROTTLE_MINUTOS)
        expiradas = [k for k, v in self._ultimo_envio.items() if v < limite]
        for clave in expiradas:
            del self._ultimo_envio[clave]

    def _mapear_tipo_alerta(self, tipo: TipoAlerta) -> TipoAlertaTemplate:
        """Convierte TipoAlerta (dominio) a TipoAlertaTemplate (templates)."""
        mapeo = {
            TipoAlerta.FORMULARIO_RECIBIDO: TipoAlertaTemplate.FORMULARIO_RECIBIDO,
            TipoAlerta.FORMULARIO_DEVUELTO: TipoAlertaTemplate.FORMULARIO_DEVUELTO,
            TipoAlerta.FORMULARIO_CORREGIDO: TipoAlertaTemplate.FORMULARIO_CORREGIDO,
            TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA: TipoAlertaTemplate.FORMULARIO_ENVIADO_A_FIRMA,
            TipoAlerta.FORMULARIO_FIRMADO: TipoAlertaTemplate.FORMULARIO_FIRMADO,
            TipoAlerta.FORMULARIO_RECHAZADO: TipoAlertaTemplate.FORMULARIO_RECHAZADO,
            TipoAlerta.REPORTE_FINAL_CARGADO: TipoAlertaTemplate.REPORTE_FINAL_CARGADO,
        }
        return mapeo[tipo]
