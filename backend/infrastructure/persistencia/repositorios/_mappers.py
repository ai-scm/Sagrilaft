"""
Funciones de mapeo ORM → entidades de dominio.

Concentra la traducción entre los objetos SQLAlchemy (Formulario, DocumentoAdjunto,
AccesoManual, ResultadoValidacion) y las dataclasses/entidades del dominio.
"""

from typing import Any, Dict, List, Optional

from domain.contratos import AccesoManualDatos, DocumentoDatos
from domain.formulario.entidades import FormularioDatos
from domain.validacion.resultado import ResultadoValidacionDominio
from infrastructure.persistencia.models import (
    AccesoManual,
    DocumentoAdjunto,
    Formulario,
    ResultadoValidacion,
)

from ._helpers import _deserializar_json, _fila_orm_a_dict, _normalizar_enum_str
from ._formulario_helpers import _TABLAS_LISTA_FORMULARIO, _valor_contacto


def _orm_formulario_a_datos(
    orm: Formulario, *, cargar_relaciones: bool = False
) -> FormularioDatos:
    """Mapea un ORM Formulario a la entidad de dominio FormularioDatos."""
    validaciones: List[Dict[str, Any]] = []
    documentos: List[DocumentoDatos] = []

    if cargar_relaciones:
        documentos = [_orm_documento_a_datos(d) for d in orm.documentos]
        validaciones = [
            {
                "id":               v.id,
                "tipo":             v.tipo,
                "campo":            v.campo,
                "resultado":        v.resultado,
                "detalle":          v.detalle,
                "valor_formulario": v.valor_formulario,
                "valor_documento":  v.valor_documento,
                "created_at":       v.created_at,
            }
            for v in orm.validaciones
        ]

    return FormularioDatos(
        id=orm.id,
        codigo_peticion=orm.codigo_peticion,
        estado=orm.estado,
        numero_correccion=orm.numero_correccion or 0,
        pagina_actual=orm.pagina_actual,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        tipo_contraparte=_normalizar_enum_str(orm.tipo_contraparte),
        tipo_persona=orm.tipo_persona,
        tipo_solicitud=orm.tipo_solicitud,
        clasificacion_actividad=orm.clasificacion_actividad,
        razon_social=orm.razon_social,
        tipo_identificacion=orm.tipo_identificacion,
        numero_identificacion=orm.numero_identificacion,
        digito_verificacion=orm.digito_verificacion,
        direccion=orm.direccion,
        pais=orm.pais,
        departamento=orm.departamento,
        ciudad=orm.ciudad,
        telefono=orm.telefono,
        fax=orm.fax,
        correo=orm.correo,
        codigo_ica=orm.codigo_ica,
        pagina_web=orm.pagina_web,
        nombre_representante=orm.nombre_representante,
        tipo_doc_representante=orm.tipo_doc_representante,
        numero_doc_representante=orm.numero_doc_representante,
        fecha_expedicion=orm.fecha_expedicion,
        ciudad_expedicion=orm.ciudad_expedicion,
        nacionalidad=orm.nacionalidad,
        fecha_nacimiento=orm.fecha_nacimiento,
        ciudad_nacimiento=orm.ciudad_nacimiento,
        profesion=orm.profesion,
        correo_representante=orm.correo_representante,
        telefono_representante=orm.telefono_representante,
        direccion_funciones=orm.direccion_funciones,
        pais_funciones=orm.pais_funciones,
        departamento_funciones=orm.departamento_funciones,
        ciudad_funciones=orm.ciudad_funciones,
        direccion_residencia=orm.direccion_residencia,
        ciudad_residencia=orm.ciudad_residencia,
        moneda_declaracion=orm.moneda_declaracion,
        moneda_declaracion_otra=orm.moneda_declaracion_otra,
        actividad_economica=orm.actividad_economica,
        codigo_ciiu=orm.codigo_ciiu,
        ingresos_mensuales=orm.ingresos_mensuales,
        otros_ingresos=orm.otros_ingresos,
        egresos_mensuales=orm.egresos_mensuales,
        total_activos=orm.total_activos,
        total_pasivos=orm.total_pasivos,
        patrimonio=orm.patrimonio,
        realiza_operaciones_moneda_extranjera=orm.realiza_operaciones_moneda_extranjera,
        paises_operaciones=orm.paises_operaciones,
        tipos_transaccion=[fila.tipo for fila in orm.tipos_transaccion],
        tipos_transaccion_otros=orm.tipos_transaccion_otros,
        actividad_clasificacion=orm.actividad_clasificacion,
        actividad_especifica=orm.actividad_especifica,
        sector=orm.sector,
        superintendencia=orm.superintendencia,
        responsabilidades_renta=orm.responsabilidades_renta,
        autorretenedor=orm.autorretenedor,
        responsabilidades_iva=orm.responsabilidades_iva,
        regimen_iva=orm.regimen_iva,
        gran_contribuyente=orm.gran_contribuyente,
        entidad_sin_animo_lucro=orm.entidad_sin_animo_lucro,
        retencion_ica=orm.retencion_ica,
        impuesto_ica=orm.impuesto_ica,
        entidad_oficial=orm.entidad_oficial,
        exento_retencion_fuente=orm.exento_retencion_fuente,
        contacto_ordenes_nombre=_valor_contacto(orm, "ordenes", "nombre"),
        contacto_ordenes_cargo=_valor_contacto(orm, "ordenes", "cargo"),
        contacto_ordenes_telefono=_valor_contacto(orm, "ordenes", "telefono"),
        contacto_ordenes_correo=_valor_contacto(orm, "ordenes", "correo"),
        contacto_pagos_nombre=_valor_contacto(orm, "pagos", "nombre"),
        contacto_pagos_cargo=_valor_contacto(orm, "pagos", "cargo"),
        contacto_pagos_telefono=_valor_contacto(orm, "pagos", "telefono"),
        contacto_pagos_correo=_valor_contacto(orm, "pagos", "correo"),
        autorizacion_datos=orm.autorizacion_datos,
        declaracion_origen_fondos=orm.declaracion_origen_fondos,
        origen_fondos=orm.origen_fondos,
        dia_firma=orm.dia_firma,
        mes_firma=orm.mes_firma,
        year_firma=orm.year_firma,
        ciudad_firma=orm.ciudad_firma,
        campos_a_corregir=orm.campos_a_corregir,
        zoho_request_id=orm.zoho_request_id,
        ruta_documento_firmado=orm.ruta_documento_firmado,
        sagrilaft_reporte_id=orm.sagrilaft_reporte_id,
        junta_directiva=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["junta_directiva"][1]) for f in orm.junta_directiva],
        accionistas=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["accionistas"][1]) for f in orm.accionistas],
        beneficiario_final=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["beneficiario_final"][1]) for f in orm.beneficiario_final],
        referencias_comerciales=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["referencias_comerciales"][1]) for f in orm.referencias_comerciales],
        referencias_bancarias=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["referencias_bancarias"][1]) for f in orm.referencias_bancarias],
        informacion_bancaria_pagos=[_fila_orm_a_dict(f, _TABLAS_LISTA_FORMULARIO["informacion_bancaria_pagos"][1]) for f in orm.informacion_bancaria_pagos],
        documentos=documentos,
        validaciones=validaciones,
        alertas_inconsistencia=[
            {
                "id": a.id,
                "formulario_id": a.formulario_id,
                "tipo_campo": a.tipo_campo,
                "nombre_documento": a.nombre_documento,
                "valor_formulario": a.valor_formulario,
                "valor_documento": a.valor_documento,
                "seccion_referencia": a.seccion_referencia,
                "estado_auditoria": a.estado_auditoria,
                "actualizado_por": a.actualizado_por,
                "fecha_creacion": a.fecha_creacion,
            }
            for a in orm.alertas_inconsistencia
        ] if cargar_relaciones else [],
    )


def _orm_acceso_manual_a_datos(
    orm: AccesoManual, *, con_formulario: bool = False
) -> AccesoManualDatos:
    """Mapea un ORM AccesoManual a AccesoManualDatos. Con con_formulario=True incluye estado y código."""
    estado_formulario = ""
    codigo_peticion = ""
    if con_formulario and getattr(orm, "formulario", None) is not None:
        estado_formulario = orm.formulario.estado or ""
        codigo_peticion = orm.formulario.codigo_peticion or ""
    return AccesoManualDatos(
        id=orm.id,
        formulario_id=orm.formulario_id,
        razon_social=orm.razon_social,
        correo_destinatario=orm.correo_destinatario,
        tipo_contraparte=_normalizar_enum_str(orm.tipo_contraparte),
        area_responsable=_normalizar_enum_str(orm.area_responsable),
        pin_hash=orm.pin_hash or "",
        token_diligenciamiento=orm.token_diligenciamiento or "",
        consumed_at=orm.consumed_at,
        expires_at=orm.expires_at,
        created_at=orm.created_at,
        ultimo_envio_correo=orm.ultimo_envio_correo,
        estado_formulario=estado_formulario,
        codigo_peticion=codigo_peticion,
    )


def _orm_validacion_a_dominio(orm: ResultadoValidacion) -> ResultadoValidacionDominio:
    """Mapea un ORM ResultadoValidacion a ResultadoValidacionDominio."""
    return ResultadoValidacionDominio(
        id=orm.id,
        formulario_id=orm.formulario_id,
        tipo=orm.tipo,
        campo=orm.campo,
        resultado=orm.resultado,
        detalle=orm.detalle,
        valor_formulario=orm.valor_formulario,
        valor_documento=orm.valor_documento,
        created_at=orm.created_at,
    )


def _orm_documento_a_datos(orm: DocumentoAdjunto) -> DocumentoDatos:
    """Mapea un ORM DocumentoAdjunto a la entidad de dominio DocumentoDatos."""
    return DocumentoDatos(
        id=orm.id,
        formulario_id=orm.formulario_id,
        tipo_documento=orm.tipo_documento,
        nombre_archivo=orm.nombre_archivo,
        ruta_archivo=orm.ruta_archivo,
        content_type=orm.content_type,
        tamano=orm.tamano,
        deleted_at=orm.deleted_at,
        created_at=orm.created_at,
        version_numero=orm.version_numero or 1,
        version_anterior_id=orm.version_anterior_id,
        hash_sha256=orm.hash_sha256,
        subido_por=orm.subido_por,
        snapshot_datos=_deserializar_json(orm.snapshot_datos),
    )
