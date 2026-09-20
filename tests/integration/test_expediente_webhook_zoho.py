import hashlib
import hmac
import json

import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _firma_hmac_zoho(cuerpo: bytes) -> str:
    return hmac.new(b"zoho-webhook-test", cuerpo, hashlib.sha256).hexdigest()


def _aprobar_y_enviar_a_firma(cliente_api, formulario_id: str) -> str:
    respuesta_aprobacion = cliente_api.post(f"/api/expedientes/{formulario_id}/aprobar")
    assert respuesta_aprobacion.status_code == 200, respuesta_aprobacion.text

    respuesta_firma = cliente_api.post(f"/api/expedientes/{formulario_id}/enviar-a-firma")
    assert respuesta_firma.status_code == 200, respuesta_firma.text
    return respuesta_firma.json()["request_id"]


def _enviar_webhook_completado(cliente_api, request_id: str):
    payload = {
        "notifications": {"operation_type": "RequestCompleted"},
        "requests": {
            "request_id": request_id,
            "request_status": "Completed",
        },
    }
    cuerpo = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return cliente_api.post(
        "/api/webhooks/zoho-sign",
        content=cuerpo,
        headers={
            "content-type": "application/json",
            "X-ZS-WEBHOOK-SIGNATURE": _firma_hmac_zoho(cuerpo),
        },
    )


def test_webhook_zoho_con_hmac_valido_completa_firma_y_conserva_documento(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    request_id = _aprobar_y_enviar_a_firma(cliente_api, acceso["formulario_id"])
    respuesta = _enviar_webhook_completado(cliente_api, request_id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"ok": True}

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    evento_firma_completada = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FIRMA_COMPLETADA,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.FIRMADO.value
    assert formulario.zoho_request_id == request_id
    assert formulario.ruta_documento_firmado is not None
    assert formulario.ruta_documento_firmado.endswith(f"formulario_firmado_{request_id}.pdf")
    assert dependencias_dobles["storage"].existe(formulario.ruta_documento_firmado)
    assert evento_firma_completada.estado_anterior == EstadoFormulario.PENDIENTE_FIRMA.value
    assert evento_firma_completada.estado_nuevo == EstadoFormulario.FIRMADO.value
    assert evento_firma_completada.actor_id == request_id
    assert evento_firma_completada.actor_tipo == ActorTipo.SISTEMA

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA,
        TipoAlerta.FORMULARIO_FIRMADO,
    ]
    assert dependencias_dobles["alertas_portal"].eventos[-1]["formulario_id"] == acceso[
        "formulario_id"
    ]

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.FIRMADO.value
    assert detalle["documento_firmado_disponible"] is True

    respuesta_descarga = cliente_api.get(
        f"/api/expedientes/{acceso['formulario_id']}/documento-firmado"
    )
    assert respuesta_descarga.status_code == 200, respuesta_descarga.text
    assert respuesta_descarga.content == dependencias_dobles["zoho_sign"].contenido_firmado


def test_webhook_zoho_duplicado_es_idempotente_y_no_duplica_efectos(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    request_id = _aprobar_y_enviar_a_firma(cliente_api, acceso["formulario_id"])

    primera_respuesta = _enviar_webhook_completado(cliente_api, request_id)
    assert primera_respuesta.status_code == 200, primera_respuesta.text

    sesion_bd.expire_all()
    formulario_firmado = (
        sesion_bd.query(Formulario)
        .filter_by(id=acceso["formulario_id"])
        .one()
    )
    ruta_firmada = formulario_firmado.ruta_documento_firmado
    eventos_iniciales = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FIRMA_COMPLETADA,
        )
        .all()
    )
    alertas_iniciales = list(dependencias_dobles["alertas_portal"].eventos)

    segunda_respuesta = _enviar_webhook_completado(cliente_api, request_id)

    assert segunda_respuesta.status_code == 200, segunda_respuesta.text
    assert segunda_respuesta.json() == {"ok": True}

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    eventos_finales = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FIRMA_COMPLETADA,
        )
        .all()
    )

    assert formulario.estado == EstadoFormulario.FIRMADO.value
    assert formulario.zoho_request_id == request_id
    assert formulario.ruta_documento_firmado == ruta_firmada
    assert dependencias_dobles["storage"].existe(ruta_firmada)
    assert len(eventos_iniciales) == 1
    assert len(eventos_finales) == 1
    assert dependencias_dobles["alertas_portal"].eventos == alertas_iniciales


def test_webhook_zoho_con_hmac_invalido_no_modifica_expediente(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    request_id = _aprobar_y_enviar_a_firma(cliente_api, acceso["formulario_id"])
    payload = {
        "notifications": {"operation_type": "RequestCompleted"},
        "requests": {
            "request_id": request_id,
            "request_status": "Completed",
        },
    }
    cuerpo = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    respuesta = cliente_api.post(
        "/api/webhooks/zoho-sign",
        content=cuerpo,
        headers={
            "content-type": "application/json",
            "X-ZS-WEBHOOK-SIGNATURE": "firma-invalida",
        },
    )

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["detail"] == "Token de webhook inválido"

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    eventos_firma_completada = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FIRMA_COMPLETADA,
        )
        .all()
    )

    assert formulario.estado == EstadoFormulario.PENDIENTE_FIRMA.value
    assert formulario.zoho_request_id == request_id
    assert formulario.ruta_documento_firmado is None
    assert eventos_firma_completada == []
    assert dependencias_dobles["zoho_sign"].solicitudes_creadas
    assert dependencias_dobles["zoho_sign"].solicitudes_canceladas == []
    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA,
    ]

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.PENDIENTE_FIRMA.value
    assert detalle["documento_firmado_disponible"] is False

    respuesta_descarga = cliente_api.get(
        f"/api/expedientes/{acceso['formulario_id']}/documento-firmado"
    )
    assert respuesta_descarga.status_code == 404, respuesta_descarga.text
