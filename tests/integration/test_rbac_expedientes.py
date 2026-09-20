import pytest

from domain.auditoria.entidades import TipoEvento
from domain.formulario.tipos import EstadoFormulario
from infrastructure.persistencia.models import AccesoManual, EventoFormulario, Formulario
from soporte.accesos import crear_acceso_manual, solicitud_acceso_manual
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _ids_listados(cliente_api) -> set[str]:
    respuesta = cliente_api.get("/api/expedientes/")
    assert respuesta.status_code == 200, respuesta.text
    return {expediente["formulario_id"] for expediente in respuesta.json()}


def _accesos_listados(cliente_api) -> list[dict]:
    respuesta = cliente_api.get("/api/accesos-manuales/")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_rbac_filtra_y_bloquea_expedientes_por_rol_de_contraparte(
    cliente_api,
    sesion_bd,
    cambiar_usuario_portal,
):
    acceso_cliente = radicar_formulario_juridico_con_documentos(
        cliente_api,
        tipo_contraparte="cliente",
        razon_social="Cliente Integracion SAS",
        correo_destinatario="representante@cliente.com",
    )
    acceso_proveedor = radicar_formulario_juridico_con_documentos(
        cliente_api,
        tipo_contraparte="proveedor",
        razon_social="Proveedor Integracion SAS",
        correo_destinatario="representante@proveedor.com",
    )

    cambiar_usuario_portal(["acceso_clientes"], "analista.clientes@blend360.com")

    assert _ids_listados(cliente_api) == {acceso_cliente["formulario_id"]}

    respuesta_detalle_cliente = cliente_api.get(
        f"/api/expedientes/{acceso_cliente['formulario_id']}"
    )
    assert respuesta_detalle_cliente.status_code == 200, respuesta_detalle_cliente.text
    assert respuesta_detalle_cliente.json()["tipo_contraparte"] == "cliente"

    respuesta_detalle_proveedor = cliente_api.get(
        f"/api/expedientes/{acceso_proveedor['formulario_id']}"
    )
    assert respuesta_detalle_proveedor.status_code == 403, respuesta_detalle_proveedor.text
    assert respuesta_detalle_proveedor.json()["detail"] == "Acceso denegado"

    respuesta_aprobacion_proveedor = cliente_api.post(
        f"/api/expedientes/{acceso_proveedor['formulario_id']}/aprobar"
    )
    assert respuesta_aprobacion_proveedor.status_code == 403, respuesta_aprobacion_proveedor.text

    sesion_bd.expire_all()
    proveedor = (
        sesion_bd.query(Formulario)
        .filter_by(id=acceso_proveedor["formulario_id"])
        .one()
    )
    eventos_aprobacion_proveedor = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso_proveedor["formulario_id"],
            tipo_evento=TipoEvento.FORMULARIO_APROBADO,
        )
        .all()
    )
    assert proveedor.estado == EstadoFormulario.ENVIADO.value
    assert eventos_aprobacion_proveedor == []

    cambiar_usuario_portal(["acceso_proveedores"], "analista.proveedores@blend360.com")

    assert _ids_listados(cliente_api) == {acceso_proveedor["formulario_id"]}
    respuesta_detalle_cliente_bloqueado = cliente_api.get(
        f"/api/expedientes/{acceso_cliente['formulario_id']}"
    )
    assert respuesta_detalle_cliente_bloqueado.status_code == 403

    cambiar_usuario_portal(
        ["acceso_clientes", "acceso_proveedores"],
        "analista.integral@blend360.com",
    )

    assert _ids_listados(cliente_api) == {
        acceso_cliente["formulario_id"],
        acceso_proveedor["formulario_id"],
    }
    respuesta_aprobacion_cliente = cliente_api.post(
        f"/api/expedientes/{acceso_cliente['formulario_id']}/aprobar"
    )
    assert respuesta_aprobacion_cliente.status_code == 200, respuesta_aprobacion_cliente.text
    assert respuesta_aprobacion_cliente.json() == {
        "estado": EstadoFormulario.VALIDADO.value
    }


def test_rbac_usuario_sin_roles_no_puede_listar_expedientes(
    cliente_api,
    cambiar_usuario_portal,
):
    radicar_formulario_juridico_con_documentos(cliente_api)
    cambiar_usuario_portal([], "analista.sin.roles@blend360.com")

    respuesta = cliente_api.get("/api/expedientes/")

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["detail"] == "Acceso denegado"


def test_rbac_filtra_y_bloquea_accesos_manuales_por_rol_de_contraparte(
    cliente_api,
    sesion_bd,
    cambiar_usuario_portal,
):
    acceso_cliente = crear_acceso_manual(
        cliente_api,
        tipo_contraparte="cliente",
        razon_social="Cliente Acceso SAS",
        correo_destinatario="acceso.cliente@example.com",
    )
    acceso_proveedor = crear_acceso_manual(
        cliente_api,
        tipo_contraparte="proveedor",
        razon_social="Proveedor Acceso SAS",
        correo_destinatario="acceso.proveedor@example.com",
    )
    acceso_proveedor_db = (
        sesion_bd.query(AccesoManual)
        .filter_by(formulario_id=acceso_proveedor["formulario_id"])
        .one()
    )
    ultimo_envio_proveedor = acceso_proveedor_db.ultimo_envio_correo

    cambiar_usuario_portal(["acceso_clientes"], "analista.clientes@blend360.com")

    accesos_cliente = _accesos_listados(cliente_api)
    assert {acceso["formulario_id"] for acceso in accesos_cliente} == {
        acceso_cliente["formulario_id"]
    }

    respuesta_crear_proveedor = cliente_api.post(
        "/api/accesos-manuales/",
        json=solicitud_acceso_manual(
            tipo_contraparte="proveedor",
            razon_social="Proveedor Bloqueado SAS",
            correo_destinatario="proveedor.bloqueado@example.com",
        ),
    )
    assert respuesta_crear_proveedor.status_code == 403, respuesta_crear_proveedor.text
    assert respuesta_crear_proveedor.json()["detail"] == "Acceso denegado"

    respuesta_reenvio_proveedor = cliente_api.post(
        f"/api/accesos-manuales/{acceso_proveedor_db.id}/reenviar"
    )
    assert respuesta_reenvio_proveedor.status_code == 403, respuesta_reenvio_proveedor.text

    sesion_bd.expire_all()
    assert (
        sesion_bd.query(AccesoManual)
        .filter_by(correo_destinatario="proveedor.bloqueado@example.com")
        .count()
        == 0
    )
    proveedor_sin_reenvio = (
        sesion_bd.query(AccesoManual)
        .filter_by(id=acceso_proveedor_db.id)
        .one()
    )
    assert proveedor_sin_reenvio.ultimo_envio_correo == ultimo_envio_proveedor

    cambiar_usuario_portal(["acceso_proveedores"], "analista.proveedores@blend360.com")

    accesos_proveedor = _accesos_listados(cliente_api)
    assert {acceso["formulario_id"] for acceso in accesos_proveedor} == {
        acceso_proveedor["formulario_id"]
    }

    cambiar_usuario_portal(
        ["acceso_clientes", "acceso_proveedores"],
        "analista.integral@blend360.com",
    )

    assert {acceso["formulario_id"] for acceso in _accesos_listados(cliente_api)} == {
        acceso_cliente["formulario_id"],
        acceso_proveedor["formulario_id"],
    }


def test_rbac_usuario_sin_roles_no_puede_listar_accesos_manuales(
    cliente_api,
    cambiar_usuario_portal,
):
    crear_acceso_manual(cliente_api)
    cambiar_usuario_portal([], "analista.sin.roles@blend360.com")

    respuesta = cliente_api.get("/api/accesos-manuales/")

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["detail"] == "Acceso denegado"
