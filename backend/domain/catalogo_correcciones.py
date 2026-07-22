"""
Catálogo de campos identificables en una solicitud de devolución.

Fuente única de verdad sobre qué campos del formulario pueden ser referenciados
explícitamente por un área al devolver un expediente para corrección.

Agregar nuevos campos aquí es la única acción necesaria para extender el sistema.
"""

from __future__ import annotations

# IDs de campo válidos que un área puede marcar como "requiere corrección".
# Deben coincidir exactamente con los IDs usados en el catálogo del frontend
# (frontend/src/data/catalogoCorrecciones.js).
CAMPOS_CORREGIBLES: frozenset[str] = frozenset({
    # Paso 1 — Documentos Adjuntos
    "doc_cedula_representante",
    "doc_certificado_existencia",
    "doc_estados_financieros",
    "doc_declaracion_renta",
    "doc_rut",
    "doc_referencias_bancarias",

    # Paso 2 — Información básica
    "tipo_contraparte",
    "tipo_persona",
    "tipo_solicitud",
    "clasificacion_actividad",
    "razon_social",
    "tipo_identificacion",
    "numero_identificacion",
    "digito_verificacion",
    "direccion",
    "pais",
    "departamento",
    "ciudad",
    "telefono",
    "fax",
    "correo",
    "codigo_ica",
    "pagina_web",

    # Paso 3 — Representante legal
    "nombre_representante",
    "tipo_doc_representante",
    "numero_doc_representante",
    "fecha_expedicion",
    "ciudad_expedicion",
    "nacionalidad",
    "fecha_nacimiento",
    "ciudad_nacimiento",
    "profesion",
    "correo_representante",
    "telefono_representante",
    "direccion_funciones",
    "pais_funciones",
    "departamento_funciones",
    "ciudad_funciones",
    "ciudad_residencia",
    "direccion_residencia",

    # Paso 4 — Junta, accionistas, beneficiarios (secciones de tabla)
    "junta_directiva",
    "accionistas",
    "beneficiario_final",

    # Paso 5 — Información financiera
    "moneda_declaracion",
    "actividad_economica",
    "codigo_ciiu",
    "ingresos_mensuales",
    "otros_ingresos",
    "egresos_mensuales",
    "total_activos",
    "total_pasivos",
    "patrimonio",

    # Paso 6 — Operaciones en moneda extranjera
    "realiza_operaciones_moneda_extranjera",
    "paises_operaciones",
    "tipos_transaccion",
    "referencias_comerciales",
    "referencias_bancarias",

    # Paso 7 — Clasificación y contactos
    "actividad_clasificacion",
    "sector",
    "superintendencia",
    "contacto_ordenes_nombre",
    "contacto_ordenes_cargo",
    "contacto_ordenes_telefono",
    "contacto_ordenes_correo",
    "contacto_pagos_nombre",
    "contacto_pagos_cargo",
    "contacto_pagos_telefono",
    "contacto_pagos_correo",
    "informacion_bancaria_pagos",

    # Paso 8 — Declaraciones y firma
    "origen_fondos",
    "dia_firma",
    "mes_firma",
    "year_firma",
    "ciudad_firma",
})


# Etiquetas legibles de cada campo identificable.
# Se usan en el correo de notificación para que la contraparte entienda
# qué campos corregir sin necesidad de abrir el formulario.
ETIQUETAS_CAMPOS_CORREGIBLES: dict[str, str] = {
    "doc_cedula_representante": "Cédula del Representante Legal",
    "doc_certificado_existencia": "Certificado de Existencia y Representación Legal",
    "doc_estados_financieros": "Estados Financieros",
    "doc_declaracion_renta": "Declaración de Renta",
    "doc_rut": "RUT (Registro Único Tributario)",
    "doc_referencias_bancarias": "Referencias Bancarias",
    "tipo_contraparte":        "Tipo de Contraparte",
    "tipo_persona":            "Tipo de Persona",
    "tipo_solicitud":          "Tipo de Solicitud",
    "clasificacion_actividad": "Clasificación de Actividad",
    "razon_social":            "Razón Social / Nombre",
    "tipo_identificacion":     "Tipo de Identificación",
    "numero_identificacion":   "Número de Identificación / NIT",
    "digito_verificacion":     "Dígito de Verificación",
    "direccion":               "Dirección",
    "pais":                    "País",
    "departamento":            "Departamento",
    "ciudad":                  "Ciudad",
    "telefono":                "Teléfono",
    "fax":                     "Fax",
    "correo":                  "Correo Electrónico",
    "codigo_ica":              "Código ICA",
    "pagina_web":              "Página Web",
    "nombre_representante":    "Nombre del Representante Legal",
    "tipo_doc_representante":  "Tipo de Documento del Representante",
    "numero_doc_representante":"Número de Documento del Representante",
    "fecha_expedicion":        "Fecha de Expedición del Documento",
    "ciudad_expedicion":       "Ciudad de Expedición",
    "nacionalidad":            "Nacionalidad",
    "fecha_nacimiento":        "Fecha de Nacimiento",
    "ciudad_nacimiento":       "Ciudad de Nacimiento",
    "profesion":               "Profesión",
    "correo_representante":    "Correo del Representante",
    "telefono_representante":  "Teléfono del Representante",
    "direccion_funciones":     "Dirección donde desempeña funciones",
    "pais_funciones":          "País de funciones",
    "departamento_funciones":  "Departamento de funciones",
    "ciudad_funciones":        "Ciudad de funciones",
    "ciudad_residencia":       "Ciudad de Residencia (Persona Natural)",
    "direccion_residencia":    "Dirección de Residencia (Persona Natural)",
    "junta_directiva":         "Miembros de Junta Directiva",
    "accionistas":             "Accionistas",
    "beneficiario_final":      "Beneficiarios Finales",
    "moneda_declaracion":      "Moneda de Declaración",
    "actividad_economica":     "Actividad Económica",
    "codigo_ciiu":             "Código CIIU",
    "ingresos_mensuales":      "Ingresos Mensuales",
    "otros_ingresos":          "Otros Ingresos",
    "egresos_mensuales":       "Egresos Mensuales",
    "total_activos":           "Total Activos",
    "total_pasivos":           "Total Pasivos",
    "patrimonio":              "Patrimonio",
    "realiza_operaciones_moneda_extranjera": "¿Realiza Operaciones en Moneda Extranjera?",
    "paises_operaciones":      "Países de Operaciones",
    "tipos_transaccion":       "Tipos de Transacción",
    "referencias_comerciales": "Referencias Comerciales",
    "referencias_bancarias":   "Referencias Bancarias",
    "actividad_clasificacion": "Actividad / Clasificación",
    "sector":                  "Sector Económico",
    "superintendencia":        "Superintendencia",
    "contacto_ordenes_nombre": "Contacto Órdenes — Nombre",
    "contacto_ordenes_cargo":  "Contacto Órdenes — Cargo",
    "contacto_ordenes_telefono": "Contacto Órdenes — Teléfono",
    "contacto_ordenes_correo": "Contacto Órdenes — Correo",
    "contacto_pagos_nombre":   "Contacto Pagos — Nombre",
    "contacto_pagos_cargo":    "Contacto Pagos — Cargo",
    "contacto_pagos_telefono": "Contacto Pagos — Teléfono",
    "contacto_pagos_correo":   "Contacto Pagos — Correo",
    "informacion_bancaria_pagos": "Información Bancaria de Pagos",
    "origen_fondos":           "Origen de Fondos",
    "dia_firma":               "Día de Firma",
    "mes_firma":               "Mes de Firma",
    "year_firma":              "Año de Firma",
    "ciudad_firma":            "Ciudad de Firma",
}


def resolver_etiquetas_campos_corregibles(campos_corregibles: list[str]) -> list[str]:
    """Convierte IDs de campo a sus etiquetas legibles para mostrar en el correo."""
    return [ETIQUETAS_CAMPOS_CORREGIBLES.get(campo, campo) for campo in campos_corregibles]


def validar_campos_corregibles(campos: list[str]) -> list[str]:
    """
    Verifica que todos los IDs de campo proporcionados existen en el catálogo.

    Raises:
        ValueError: si algún ID no es reconocido, listando los inválidos.
    """
    campos_no_corregibles = [campo for campo in campos if campo not in CAMPOS_CORREGIBLES]
    if campos_no_corregibles:
        raise ValueError(
            f"Los siguientes campos no son identificables en el formulario: {campos_no_corregibles}. "
            f"Consulte el catálogo de campos permitidos."
        )
    return campos
