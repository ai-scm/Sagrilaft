"""
Router de webhooks externos.

Actualmente maneja notificaciones de ZohoSign (firma electrónica).
ZohoSign hace POST a este endpoint cuando cambia el estado de una solicitud de firma.
"""

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Request

from api.dependencies import obtener_servicio_firma
from api.schemas import ZohoWebhookPayload
from domain.excepciones import WebhookTokenInvalidoError
from domain.utils.seguridad import sanitizar_log
from services.firma.firma_service import FirmaService

logger = logging.getLogger(__name__)

enrutador = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _normalizar_firma(valor: str) -> str:
    firma = valor.strip()
    if "=" in firma and not firma.startswith("sha256="):
        firma = firma.rsplit("=", 1)[-1].strip()
    if firma.startswith("sha256="):
        firma = firma.removeprefix("sha256=").strip()
    return firma


def _firmas_esperadas(cuerpo: bytes, secreto: str) -> set[str]:
    digest = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).digest()
    return {
        digest.hex(),
        base64.b64encode(digest).decode("ascii"),
    }


async def _leer_payload_validado(request: Request) -> ZohoWebhookPayload:
    config = request.app.state.config.zoho_sign
    header_name = config.webhook_signature_header
    firma_recibida = request.headers.get(header_name)
    cuerpo = await request.body()

    if not config.webhook_secret or not firma_recibida:
        logger.warning("Webhook ZohoSign rechazado: firma HMAC ausente")
        raise WebhookTokenInvalidoError()

    firma = _normalizar_firma(firma_recibida)
    if not any(hmac.compare_digest(firma, esperada) for esperada in _firmas_esperadas(cuerpo, config.webhook_secret)):
        logger.warning("Webhook ZohoSign rechazado: firma HMAC invalida")
        raise WebhookTokenInvalidoError()

    return ZohoWebhookPayload.model_validate_json(cuerpo)


@enrutador.post(
    "/zoho-sign",
    summary="Webhook de ZohoSign",
    description=(
        "Recibe notificaciones de ZohoSign sobre cambios de estado en solicitudes de firma. "
        "Valida la firma HMAC SHA-256 configurada con ZOHO_WEBHOOK_SECRET."
    ),
    status_code=200,
)
async def webhook_zoho_sign(
    payload: ZohoWebhookPayload = Depends(_leer_payload_validado),
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> dict:
    logger.info("Webhook ZohoSign recibido: %s", sanitizar_log(payload.notifications.operation_type))
    servicio.procesar_webhook_verificado(
        request_id=payload.requests.request_id,
        request_status=payload.requests.request_status,
    )
    return {"ok": True}
