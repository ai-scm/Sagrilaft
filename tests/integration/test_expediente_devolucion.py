import json

import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import AccesoManual, EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def test_devolver_expediente_reactiva_acceso_notifica_y_expone_correccion(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    especificaciones = (
        "Corregir la razon social y adjuntar un RUT actualizado antes de reenviar."
    )
    campos_identificados = ["razon_social", "doc_rut"]

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/devolver",
        json={
            "especificaciones": especificaciones,
            "campos_identificados": campos_identificados,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "estado": EstadoFormulario.EN_CORRECCION.value,
        "correo_notificado": acceso["correo_destinatario"],
        "correo_enviado": True,
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_reactivado = (
        sesion_bd.query(AccesoManual)
        .filter_by(formulario_id=acceso["formulario_id"])
        .one()
    )
    evento_devolucion = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FORMULARIO_DEVUELTO,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.EN_CORRECCION.value
    assert formulario.numero_correccion == 1
    assert json.loads(formulario.campos_a_corregir) == {
        "especificaciones": especificaciones,
        "campos": campos_identificados,
    }
    assert acceso_reactivado.consumed_at is None
    assert acceso_reactivado.token_diligenciamiento != acceso["token_diligenciamiento"]
    assert evento_devolucion.estado_anterior == EstadoFormulario.ENVIADO.value
    assert evento_devolucion.estado_nuevo == EstadoFormulario.EN_CORRECCION.value
    assert evento_devolucion.actor_id == "analista.integracion@blend360.com"
    assert evento_devolucion.actor_tipo == ActorTipo.OPERADOR
    metadata_devolucion = json.loads(evento_devolucion.metadata_json)
    assert metadata_devolucion["numero_correccion"] == 1
    assert metadata_devolucion["especificaciones"] == especificaciones
    assert metadata_devolucion["campos"] == campos_identificados

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_DEVUELTO,
    ]
    alerta_devolucion = dependencias_dobles["alertas_portal"].eventos[-1]
    assert alerta_devolucion["formulario_id"] == acceso["formulario_id"]
    assert alerta_devolucion["detalle"].startswith("Corrección #1")
    assert "Razón Social / Nombre" in alerta_devolucion["detalle"]
    assert "RUT (Registro Único Tributario)" in alerta_devolucion["detalle"]

    assert dependencias_dobles["notificador"].devoluciones == [
        {
            "correo_destinatario": acceso["correo_destinatario"],
            "especificaciones_correccion": especificaciones,
            "enlace_diligenciamiento": f"http://frontend.test/?token={acceso_reactivado.token_diligenciamiento}",
            "campos_identificados": campos_identificados,
        }
    ]

    respuesta_token_viejo = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )
    assert respuesta_token_viejo.status_code == 404, respuesta_token_viejo.text

    respuesta_token_nuevo = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso_reactivado.token_diligenciamiento}"
    )
    assert respuesta_token_nuevo.status_code == 200, respuesta_token_nuevo.text
    formulario_por_token = respuesta_token_nuevo.json()
    assert formulario_por_token["id"] == acceso["formulario_id"]
    assert formulario_por_token["estado"] == EstadoFormulario.EN_CORRECCION.value
    assert formulario_por_token["campos_a_corregir"] == formulario.campos_a_corregir

    respuesta_recuperacion = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json={
            "codigo_peticion": acceso["codigo_peticion"],
            "pin": acceso["pin"],
        },
    )

    assert respuesta_recuperacion.status_code == 200, respuesta_recuperacion.text
    formulario_recuperado = respuesta_recuperacion.json()
    assert formulario_recuperado["id"] == acceso["formulario_id"]
    assert formulario_recuperado["estado"] == EstadoFormulario.EN_CORRECCION.value
    assert formulario_recuperado["campos_a_corregir"] == formulario.campos_a_corregir

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.EN_CORRECCION.value
    assert detalle["modo_trabajo"] == "correccion"
    assert detalle["numero_correccion"] == 1
    assert detalle["campos_a_corregir"] == formulario.campos_a_corregir
