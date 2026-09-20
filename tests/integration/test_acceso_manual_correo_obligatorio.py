import pytest

from soporte.accesos import solicitud_acceso_manual

pytestmark = pytest.mark.integration


def test_creacion_acceso_manual_exige_correo_destinatario(cliente_api):
    solicitud = solicitud_acceso_manual()
    solicitud.pop("correo_destinatario")

    respuesta = cliente_api.post("/api/accesos-manuales/", json=solicitud)

    assert respuesta.status_code == 422


def test_creacion_acceso_manual_rechaza_correo_destinatario_invalido(cliente_api):
    respuesta = cliente_api.post(
        "/api/accesos-manuales/",
        json=solicitud_acceso_manual(correo_destinatario="correo-invalido"),
    )

    assert respuesta.status_code == 422


def test_creacion_acceso_manual_con_correo_genera_credenciales_y_notifica(
    cliente_api,
    dependencias_dobles,
):
    correo_destinatario = "representante@proveedor.com"

    respuesta = cliente_api.post(
        "/api/accesos-manuales/",
        json=solicitud_acceso_manual(correo_destinatario=correo_destinatario),
    )

    assert respuesta.status_code == 201, respuesta.text
    acceso = respuesta.json()
    assert acceso["correo_destinatario"] == correo_destinatario
    assert acceso["correo_enviado"] is True
    assert acceso["formulario_id"]
    assert acceso["codigo_peticion"]
    assert acceso["pin"]
    assert acceso["token_diligenciamiento"]
    assert acceso["enlace_diligenciamiento"].endswith(
        f"?token={acceso['token_diligenciamiento']}"
    )

    notificador = dependencias_dobles["notificador"]
    assert len(notificador.accesos_creados) == 1
    assert notificador.accesos_creados[0]["correo_destinatario"] == correo_destinatario
    assert notificador.accesos_creados[0]["codigo_peticion"] == acceso["codigo_peticion"]
    assert notificador.accesos_creados[0]["pin"] == acceso["pin"]
