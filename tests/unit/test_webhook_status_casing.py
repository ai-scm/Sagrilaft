"""
ZohoSign real envia request_status en minuscula ('completed', 'declined',
'expired'), no capitalizado ('Completed') como asumia procesar_webhook_
verificado. Confirmado en logs reales de staging 2026-09-24: el webhook
llegaba, pasaba la validacion HMAC, pero el formulario se quedaba en
PENDIENTE_FIRMA para siempre porque "completed" != "Completed" caia
siempre al branch de "no requiere accion". El test de integracion
existente construia su payload de prueba con "Completed" (el mismo valor
que el codigo esperaba), por lo que nunca detecto el problema.
"""
from unittest.mock import MagicMock, patch

from domain.formulario.entidades import FormularioDatos
from services.firma.firma_service import FirmaService


def _formulario(zoho_request_id: str = "zoho-req-1") -> FormularioDatos:
    return FormularioDatos(
        id="f-1",
        codigo_peticion="SAG-00000001",
        estado="PENDIENTE_FIRMA",
        zoho_request_id=zoho_request_id,
    )


def _crear_servicio(formulario: FormularioDatos) -> FirmaService:
    repo = MagicMock()
    repo.obtener_formulario_por_zoho_id.return_value = formulario
    return FirmaService(
        repo=repo,
        zoho=MagicMock(),
        storage=MagicMock(),
        webhook_secret="secret-test",
    )


def test_status_completed_minuscula_completa_la_firma():
    servicio = _crear_servicio(_formulario())

    with patch.object(servicio, "_procesar_firma_completada") as completada_mock:
        servicio.procesar_webhook_verificado(request_id="zoho-req-1", request_status="completed")

    completada_mock.assert_called_once()


def test_status_completed_mayuscula_tambien_completa_la_firma():
    servicio = _crear_servicio(_formulario())

    with patch.object(servicio, "_procesar_firma_completada") as completada_mock:
        servicio.procesar_webhook_verificado(request_id="zoho-req-1", request_status="Completed")

    completada_mock.assert_called_once()


def test_status_declined_minuscula_cancela_la_firma():
    servicio = _crear_servicio(_formulario())

    with patch.object(servicio, "_procesar_firma_cancelada") as cancelada_mock:
        servicio.procesar_webhook_verificado(request_id="zoho-req-1", request_status="declined")

    cancelada_mock.assert_called_once()


def test_status_expired_minuscula_cancela_la_firma():
    servicio = _crear_servicio(_formulario())

    with patch.object(servicio, "_procesar_firma_cancelada") as cancelada_mock:
        servicio.procesar_webhook_verificado(request_id="zoho-req-1", request_status="expired")

    cancelada_mock.assert_called_once()


def test_status_inprogress_no_completa_ni_cancela():
    servicio = _crear_servicio(_formulario())

    with patch.object(servicio, "_procesar_firma_completada") as completada_mock, \
         patch.object(servicio, "_procesar_firma_cancelada") as cancelada_mock:
        servicio.procesar_webhook_verificado(request_id="zoho-req-1", request_status="inprogress")

    completada_mock.assert_not_called()
    cancelada_mock.assert_not_called()
