"""
Router de webhooks externos.

Actualmente maneja notificaciones de ZohoSign (firma electrónica).
ZohoSign hace POST a este endpoint cuando cambia el estado de una solicitud de firma.
"""

import logging

from fastapi import APIRouter, Depends

from api.dependencies import obtener_servicio_firma
from api.schemas import ZohoWebhookPayload
from domain.utils.seguridad import sanitizar_log
from services.firma.firma_service import FirmaService

logger = logging.getLogger(__name__)

enrutador = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@enrutador.post(
    "/zoho-sign",
    summary="Webhook de ZohoSign",
    description=(
        "Recibe notificaciones de ZohoSign sobre cambios de estado en solicitudes de firma. "
        "Valida el secret_token configurado en ZOHO_WEBHOOK_SECRET."
    ),
    status_code=200,
)
def webhook_zoho_sign(
    payload: ZohoWebhookPayload,
    servicio: FirmaService = Depends(obtener_servicio_firma),
) -> dict:
    logger.info("Webhook ZohoSign recibido: %s", sanitizar_log(payload.notifications.operation_type))
    servicio.procesar_webhook(
        secret_token=payload.notifications.secret_token,
        request_id=payload.requests.request_id,
        request_status=payload.requests.request_status,
    )
    return {"ok": True}
