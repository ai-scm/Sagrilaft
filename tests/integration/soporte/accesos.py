def solicitud_acceso_manual(**sobrescrituras):
    """Payload valido para crear un acceso manual desde el portal interno."""

    datos = {
        "tipo_contraparte": "proveedor",
        "razon_social": "Proveedor Integracion SAS",
        "area_responsable": "legal",
        "correo_destinatario": "representante@proveedor.com",
    }
    datos.update(sobrescrituras)
    return datos


def crear_acceso_manual(cliente_api, **sobrescrituras):
    """Crea un acceso manual valido y retorna la respuesta JSON."""

    respuesta = cliente_api.post(
        "/api/accesos-manuales/",
        json=solicitud_acceso_manual(**sobrescrituras),
    )

    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()
