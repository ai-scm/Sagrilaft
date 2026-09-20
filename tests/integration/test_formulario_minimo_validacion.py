import pytest

from soporte.accesos import crear_acceso_manual
from soporte.formularios import formulario_minimo_juridica_para_envio


pytestmark = pytest.mark.integration


def _campos_con_error(respuesta_envio):
    return {error["campo"] for error in respuesta_envio["errores"]}


def test_envio_de_formulario_incompleto_retorna_errores_sin_consumir_acceso(
    cliente_api,
):
    acceso = crear_acceso_manual(cliente_api)

    respuesta_envio = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={"credenciales": {"token_diligenciamiento": acceso["token_diligenciamiento"]}},
    )

    assert respuesta_envio.status_code == 200, respuesta_envio.text
    resultado = respuesta_envio.json()
    assert resultado["valido"] is False
    assert {
        "tipo_persona",
        "tipo_solicitud",
        "numero_identificacion",
        "autorizacion_datos",
        "declaracion_origen_fondos",
    }.issubset(_campos_con_error(resultado))

    respuesta_token = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )
    assert respuesta_token.status_code == 200, respuesta_token.text
    assert respuesta_token.json()["estado"] == "borrador"


def test_formulario_minimo_juridica_se_autoguarda_y_se_recupera(cliente_api):
    acceso = crear_acceso_manual(cliente_api)
    formulario_minimo = formulario_minimo_juridica_para_envio()

    respuesta_autoguardado = cliente_api.put(
        f"/api/formularios/{acceso['formulario_id']}",
        json=formulario_minimo,
    )

    assert respuesta_autoguardado.status_code == 200, respuesta_autoguardado.text
    formulario_guardado = respuesta_autoguardado.json()
    assert formulario_guardado["id"] == acceso["formulario_id"]
    assert formulario_guardado["estado"] == "borrador"
    assert formulario_guardado["tipo_persona"] == "juridica"
    assert formulario_guardado["razon_social"] == formulario_minimo["razon_social"]
    assert formulario_guardado["correo"] == formulario_minimo["correo"]
    assert formulario_guardado["pagina_actual"] == formulario_minimo["pagina_actual"]
    assert formulario_guardado["autorizacion_datos"] is True
    assert formulario_guardado["declaracion_origen_fondos"] is True

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
    assert formulario_recuperado["razon_social"] == formulario_minimo["razon_social"]
    assert formulario_recuperado["correo"] == formulario_minimo["correo"]
    assert formulario_recuperado["pagina_actual"] == formulario_minimo["pagina_actual"]
    assert formulario_recuperado["junta_directiva"][0]["nombre"] == "Representante Legal"
    assert formulario_recuperado["accionistas"][0]["porcentaje"] == 60.0
    assert formulario_recuperado["beneficiario_final"][0]["porcentaje"] == 60.0
