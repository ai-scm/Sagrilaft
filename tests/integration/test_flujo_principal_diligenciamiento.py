import pytest

from soporte.accesos import crear_acceso_manual


pytestmark = pytest.mark.integration


def _crear_acceso_manual(cliente_api):
    return crear_acceso_manual(cliente_api)


def test_destinatario_entra_por_link_autoguarda_y_retoma_con_codigo_pin(cliente_api):
    acceso = _crear_acceso_manual(cliente_api)

    respuesta_link = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )

    assert respuesta_link.status_code == 200, respuesta_link.text
    formulario_por_link = respuesta_link.json()
    assert formulario_por_link["id"] == acceso["formulario_id"]
    assert formulario_por_link["codigo_peticion"] == acceso["codigo_peticion"]
    assert formulario_por_link["estado"] == "borrador"
    assert "pin" not in formulario_por_link
    assert "pin_hash" not in formulario_por_link

    datos_autoguardado = {
        "razon_social": "Proveedor Integracion SAS",
        "tipo_contraparte": "proveedor",
        "tipo_persona": "juridica",
        "correo": "contacto@proveedor.com",
        "telefono": "6015550101",
        "pagina_actual": 3,
    }

    respuesta_autoguardado = cliente_api.put(
        f"/api/formularios/{acceso['formulario_id']}",
        json=datos_autoguardado,
    )

    assert respuesta_autoguardado.status_code == 200, respuesta_autoguardado.text
    formulario_autoguardado = respuesta_autoguardado.json()
    assert formulario_autoguardado["id"] == acceso["formulario_id"]
    assert formulario_autoguardado["estado"] == "borrador"
    assert formulario_autoguardado["razon_social"] == datos_autoguardado["razon_social"]
    assert formulario_autoguardado["correo"] == datos_autoguardado["correo"]
    assert formulario_autoguardado["pagina_actual"] == datos_autoguardado["pagina_actual"]

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
    assert formulario_recuperado["codigo_peticion"] == acceso["codigo_peticion"]
    assert formulario_recuperado["estado"] == "borrador"
    assert formulario_recuperado["razon_social"] == datos_autoguardado["razon_social"]
    assert formulario_recuperado["correo"] == datos_autoguardado["correo"]
    assert formulario_recuperado["pagina_actual"] == datos_autoguardado["pagina_actual"]
    assert "pin" not in formulario_recuperado
    assert "pin_hash" not in formulario_recuperado
