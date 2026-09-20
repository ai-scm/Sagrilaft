import json

import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import AccesoManual, EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def test_rechazar_expediente_cierra_flujo_registra_trazabilidad_y_notifica(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    motivo_interno = (
        "La contraparte presenta coincidencias no mitigadas en la debida diligencia."
    )
    mensaje_destinatario = (
        "Su solicitud SAGRILAFT fue rechazada. Comuníquese con el área responsable."
    )

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/rechazar",
        json={
            "motivo": motivo_interno,
            "mensaje_para_destinatario": mensaje_destinatario,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "estado": EstadoFormulario.RECHAZADO.value,
        "motivo": motivo_interno,
        "notificacion_enviada": True,
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_consumido = (
        sesion_bd.query(AccesoManual)
        .filter_by(formulario_id=acceso["formulario_id"])
        .one()
    )
    evento_rechazo = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FORMULARIO_RECHAZADO,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.RECHAZADO.value
    assert acceso_consumido.consumed_at is not None
    assert acceso_consumido.token_diligenciamiento == acceso["token_diligenciamiento"]
    assert evento_rechazo.estado_anterior == EstadoFormulario.ENVIADO.value
    assert evento_rechazo.estado_nuevo == EstadoFormulario.RECHAZADO.value
    assert evento_rechazo.actor_id == "analista.integracion@blend360.com"
    assert evento_rechazo.actor_tipo == ActorTipo.OPERADOR
    assert json.loads(evento_rechazo.metadata_json) == {"motivo": motivo_interno}

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_RECHAZADO,
    ]
    alerta_rechazo = dependencias_dobles["alertas_portal"].eventos[-1]
    assert alerta_rechazo["formulario_id"] == acceso["formulario_id"]
    assert alerta_rechazo["detalle"] == f"Motivo interno: {motivo_interno}"

    assert dependencias_dobles["notificador"].rechazos == [
        {
            "correo_destinatario": acceso["correo_destinatario"],
            "mensaje_para_destinatario": mensaje_destinatario,
        }
    ]
    assert dependencias_dobles["notificador"].devoluciones == []

    respuesta_token_consumido = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )
    assert respuesta_token_consumido.status_code == 410, respuesta_token_consumido.text

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.RECHAZADO.value
    assert detalle["modo_trabajo"] == ""
