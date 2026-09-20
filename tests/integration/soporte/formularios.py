from copy import deepcopy


def _formulario_base_para_envio():
    """Campos comunes exigidos por ValidadorEnvioFormulario para enviar."""

    return {
        "tipo_contraparte": "proveedor",
        "tipo_solicitud": "vinculacion",
        "clasificacion_actividad": "C",
        "razon_social": "Proveedor Integracion SAS",
        "tipo_identificacion": "NIT",
        "numero_identificacion": "900123456",
        "digito_verificacion": "7",
        "direccion": "Calle 100 10 20",
        "departamento": "Bogota D.C.",
        "ciudad": "Bogota",
        "telefono": "6015550101",
        "fax": "6015550102",
        "correo": "contacto@proveedor.com",
        "pagina_web": "https://proveedor.com",
        "nombre_representante": "Representante Legal",
        "tipo_doc_representante": "CC",
        "numero_doc_representante": "10101010",
        "fecha_expedicion": "2020-01-15",
        "ciudad_expedicion": "Bogota",
        "nacionalidad": "Colombiana",
        "fecha_nacimiento": "1980-05-20",
        "ciudad_nacimiento": "Bogota",
        "profesion": "Administradora",
        "correo_representante": "representante@proveedor.com",
        "telefono_representante": "3005550101",
        "direccion_funciones": "Calle 100 10 20",
        "pais_funciones": "Colombia",
        "departamento_funciones": "Bogota D.C.",
        "ciudad_funciones": "Bogota",
        "moneda_declaracion_otra": "COP",
        "actividad_economica": "Servicios profesionales",
        "codigo_ciiu": "7020",
        "ingresos_mensuales": 10000000,
        "egresos_mensuales": 5000000,
        "total_activos": 100000000,
        "total_pasivos": 20000000,
        "patrimonio": 80000000,
        "realiza_operaciones_moneda_extranjera": False,
        "actividad_clasificacion": "Comercial",
        "actividad_especifica": "Consultoria",
        "sector": "Privado",
        "superintendencia": "No aplica",
        "responsabilidades_renta": "Declarante",
        "autorretenedor": False,
        "responsabilidades_iva": "Responsable",
        "regimen_iva": "Régimen común",
        "gran_contribuyente": False,
        "entidad_sin_animo_lucro": False,
        "retencion_ica": False,
        "impuesto_ica": True,
        "entidad_oficial": False,
        "exento_retencion_fuente": False,
        "contacto_ordenes_nombre": "Contacto Ordenes",
        "contacto_ordenes_cargo": "Compras",
        "contacto_ordenes_telefono": "6015550103",
        "contacto_ordenes_correo": "ordenes@proveedor.com",
        "contacto_pagos_nombre": "Contacto Pagos",
        "contacto_pagos_cargo": "Tesoreria",
        "contacto_pagos_telefono": "6015550104",
        "contacto_pagos_correo": "pagos@proveedor.com",
        "origen_fondos": "Ingresos propios de la operacion comercial.",
        "autorizacion_datos": True,
        "declaracion_origen_fondos": True,
        "dia_firma": 1,
        "mes_firma": 9,
        "year_firma": 2026,
        "ciudad_firma": "Bogota",
        "pagina_actual": 13,
    }


def formulario_minimo_juridica_para_envio(**sobrescrituras):
    """Payload minimo segun ValidadorEnvioFormulario para persona juridica."""

    datos = {
        **_formulario_base_para_envio(),
        "tipo_persona": "juridica",
        "junta_directiva": [
            {
                "cargo": "Representante Legal",
                "nombre": "Representante Legal",
                "tipo_id": "CC",
                "numero_id": "10101010",
                "es_pep": "no",
            }
        ],
        "accionistas": [
            {
                "nombre": "Accionista Principal",
                "tipo_id": "CC",
                "numero_id": "20202020",
                "es_pep": "no",
                "porcentaje": 60,
            }
        ],
        "beneficiario_final": [
            {
                "nombre": "Beneficiario Principal",
                "tipo_id": "CC",
                "numero_id": "30303030",
                "es_pep": "no",
                "porcentaje": 60,
            }
        ],
    }
    datos.update(sobrescrituras)
    return deepcopy(datos)


def formulario_minimo_natural_para_envio(**sobrescrituras):
    """Payload minimo segun ValidadorEnvioFormulario para persona natural."""

    datos = {
        **_formulario_base_para_envio(),
        "tipo_persona": "natural",
        "tipo_identificacion": "CC",
        "numero_identificacion": "10101010",
        "digito_verificacion": "NA",
        "direccion_residencia": "Carrera 15 90 10",
        "ciudad_residencia": "Bogota",
    }
    datos.update(sobrescrituras)
    return deepcopy(datos)
