from unittest.mock import Mock

import boto3
import pytest

from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.config.configuracion import AWSConfig, SesConfig
from infrastructure.notificaciones.email_service import _construir_mensaje
from infrastructure.notificaciones.ses_alertas import SesAlertasPortal


def test_smtp_incluye_reply_to_sin_cambiar_destinatario():
    msg = _construir_mensaje(remitente="no-reply@example.com", destinatario="cliente@example.com",
                            asunto="Prueba", cuerpo_texto="texto", cuerpo_html="<p>texto</p>",
                            responder_a="legal@example.com")
    assert msg["Reply-To"] == "legal@example.com"
    assert msg["To"] == "cliente@example.com"


@pytest.mark.parametrize("reply_to", ["legal@example.com", ""])
def test_ses_configura_respuesta_y_conserva_destinatario(monkeypatch, reply_to):
    client = Mock()
    client.send_email.return_value = {"MessageId": "test"}
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
    monkeypatch.setenv("ALERTAS_EMAIL_DESTINATARIO", "operador@example.com")
    notifier = SesAlertasPortal(SesConfig(email_origen="no-reply@example.com", habilitado=True),
                               AWSConfig(region="us-east-1"), "https://portal.example.com",
                               responder_a=reply_to)
    assert notifier.alertar(TipoAlerta.FORMULARIO_RECIBIDO, "id", "Empresa", "CLIENTE")
    request = client.send_email.call_args.kwargs
    assert request["Destination"]["ToAddresses"] == ["operador@example.com"]
    assert request.get("ReplyToAddresses") == ([reply_to] if reply_to else None)
