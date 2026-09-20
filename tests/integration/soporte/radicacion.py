from soporte.accesos import crear_acceso_manual
from soporte.documentos import subir_documentos_requeridos
from soporte.formularios import formulario_minimo_juridica_para_envio


def autoguardar_formulario_juridico_completo(
    cliente_api,
    formulario_id: str,
    **sobrescrituras,
) -> None:
    respuesta = cliente_api.put(
        f"/api/formularios/{formulario_id}",
        json=formulario_minimo_juridica_para_envio(**sobrescrituras),
    )

    assert respuesta.status_code == 200, respuesta.text


def enviar_formulario_con_token(cliente_api, acceso: dict) -> dict:
    respuesta = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": acceso["token_diligenciamiento"],
            },
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    resultado = respuesta.json()
    assert resultado["valido"] is True
    assert resultado["errores"] == []
    return resultado


def radicar_formulario_juridico_con_documentos(cliente_api, **datos_acceso) -> dict:
    acceso = crear_acceso_manual(cliente_api, **datos_acceso)
    autoguardar_formulario_juridico_completo(
        cliente_api,
        acceso["formulario_id"],
        tipo_contraparte=datos_acceso.get("tipo_contraparte", "proveedor"),
        razon_social=datos_acceso.get("razon_social", "Proveedor Integracion SAS"),
        correo=datos_acceso.get("correo_destinatario", "representante@proveedor.com"),
        correo_representante=datos_acceso.get(
            "correo_destinatario",
            "representante@proveedor.com",
        ),
    )
    subir_documentos_requeridos(cliente_api, acceso["formulario_id"])
    enviar_formulario_con_token(cliente_api, acceso)
    return acceso
