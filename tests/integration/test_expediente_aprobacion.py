import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def test_aprobar_expediente_cambia_estado_registra_auditoria_y_no_alerta(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO
    ]

    respuesta = cliente_api.post(f"/api/expedientes/{acceso['formulario_id']}/aprobar")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"estado": EstadoFormulario.VALIDADO.value}

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    evento_aprobacion = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FORMULARIO_APROBADO,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.VALIDADO.value
    assert evento_aprobacion.estado_anterior == EstadoFormulario.ENVIADO.value
    assert evento_aprobacion.estado_nuevo == EstadoFormulario.VALIDADO.value
    assert evento_aprobacion.actor_id == "analista.integracion@blend360.com"
    assert evento_aprobacion.actor_tipo == ActorTipo.OPERADOR
    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO
    ]
    assert dependencias_dobles["notificador"].rechazos == []
    assert dependencias_dobles["notificador"].devoluciones == []

    respuesta_detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}")

    assert respuesta_detalle.status_code == 200, respuesta_detalle.text
    assert respuesta_detalle.json()["estado"] == EstadoFormulario.VALIDADO.value
