"""
Implementaciones SQLAlchemy de los puertos de repositorio definidos en domain/puertos/.

Cada clase encapsula las operaciones de base de datos de un servicio específico,
eliminando el acoplamiento directo de los servicios a SQLAlchemy Session.

Todas las instancias de una misma solicitud HTTP comparten la misma Session
(FastAPI cachea Depends(get_db) por request), preservando la atomicidad
transaccional entre servicios.
"""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, joinedload

from domain.constantes import (
    TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
)
from domain.contratos import (
    AccesoManualDatos,
    DocumentoDatos,
    ResultadoCreacionAcceso,
    SolicitudCreacionAcceso,
)
from domain.formulario.entidades import FormularioDatos
from domain.validacion.resultado import ResultadoValidacionDominio
from infrastructure.persistencia.models import (
    AccesoManual,
    AccionistaFormulario,
    BeneficiarioFinalFormulario,
    ClasificacionTributariaFormulario,
    ContactoFormulario,
    CuentaPagoFormulario,
    DatosPersonaNaturalFormulario,
    DocumentoAdjunto,
    Formulario,
    MiembroJuntaDirectiva,
    ReferenciaBancariaDeclarada,
    ReferenciaComercialFormulario,
    ResultadoValidacion,
    TipoTransaccionFormulario,
    AlertaInconsistencia,
)

# Campos que se almacenan como JSON string en la base de datos.
# Deben serializarse al escribir y deserializarse al leer.
_CAMPOS_JSON = ["snapshot_datos"]

_CONTACTOS_FORMULARIO = {
    "ordenes": "contacto_ordenes",
    "pagos": "contacto_pagos",
}

_ATRIBUTOS_CONTACTO = ["nombre", "cargo", "telefono", "correo"]

_CAMPOS_PERSONA_NATURAL = [
    "direccion_residencia",
    "ciudad_residencia",
]

_CAMPOS_CLASIFICACION_TRIBUTARIA = [
    "actividad_clasificacion",
    "actividad_especifica",
    "sector",
    "superintendencia",
    "responsabilidades_renta",
    "autorretenedor",
    "responsabilidades_iva",
    "regimen_iva",
    "gran_contribuyente",
    "entidad_sin_animo_lucro",
    "retencion_ica",
    "impuesto_ica",
    "entidad_oficial",
    "exento_retencion_fuente",
]

_CAMPOS_BOOLEANOS_SI_NO = {
    "realiza_operaciones_moneda_extranjera",
    "autorretenedor",
    "gran_contribuyente",
    "entidad_sin_animo_lucro",
    "retencion_ica",
    "impuesto_ica",
    "entidad_oficial",
    "exento_retencion_fuente",
}

# Listas dinámicas del formulario que hoy viven en tablas 1:N propias
# (Cambio 1 del rediseño de esquema). Cada entrada mapea el nombre de la
# relación en Formulario -> (clase ORM hija, atributos que expone al dominio).
# Los atributos son exactamente el shape que ya esperaban dominio/API/PDF/
# validación cuando estos campos eran JSON — la costura no cambia su forma.
_TABLAS_LISTA_FORMULARIO = {
    "junta_directiva": (MiembroJuntaDirectiva, [
        "cargo", "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep",
    ]),
    "accionistas": (AccionistaFormulario, [
        "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep", "porcentaje",
    ]),
    "beneficiario_final": (BeneficiarioFinalFormulario, [
        "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep", "porcentaje",
    ]),
    "referencias_comerciales": (ReferenciaComercialFormulario, [
        "nombre_establecimiento", "persona_contacto", "telefono", "ciudad",
    ]),
    "referencias_bancarias": (ReferenciaBancariaDeclarada, ["entidad", "producto"]),
    "informacion_bancaria_pagos": (CuentaPagoFormulario, [
        "entidad_bancaria", "ciudad_oficina", "tipo_cuenta", "numero_cuenta",
    ]),
}


def _fila_orm_a_dict(fila: Any, atributos: List[str]) -> Dict[str, Any]:
    """Convierte una fila ORM hija (ej. MiembroJuntaDirectiva) al dict plano que espera el dominio."""
    return {atributo: getattr(fila, atributo) for atributo in atributos}


def _construir_filas_hijas(modelo_cls: type, atributos: List[str], valor: Any) -> List[Any]:
    """Convierte una lista de dicts (payload del cliente) en instancias ORM hijas, preservando orden."""
    filas = valor or []
    return [
        modelo_cls(orden=indice, **{atributo: fila.get(atributo) for atributo in atributos})
        for indice, fila in enumerate(filas)
    ]


def _construir_relaciones_dinamicas(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reemplaza, para las claves presentes en `datos`, las listas de dicts de las
    tablas dinámicas del formulario por listas de instancias ORM hijas listas
    para asignar a la relación (SQLAlchemy reemplaza la colección completa,
    incluyendo el borrado de las filas huérfanas gracias a delete-orphan).
    """
    resultado = dict(datos)
    for campo, (modelo_cls, atributos) in _TABLAS_LISTA_FORMULARIO.items():
        if campo in resultado:
            resultado[campo] = _construir_filas_hijas(modelo_cls, atributos, resultado[campo])
    if "tipos_transaccion" in resultado:
        resultado["tipos_transaccion"] = [
            TipoTransaccionFormulario(tipo=tipo) for tipo in (resultado["tipos_transaccion"] or [])
        ]
    return resultado


def _extraer_campos_contacto(datos: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Agrupa los campos planos contacto_* por tipo interno de contacto."""
    contactos: Dict[str, Dict[str, Any]] = {}
    for tipo, prefijo in _CONTACTOS_FORMULARIO.items():
        valores = {
            atributo: datos[f"{prefijo}_{atributo}"]
            for atributo in _ATRIBUTOS_CONTACTO
            if f"{prefijo}_{atributo}" in datos
        }
        if valores:
            contactos[tipo] = valores
    return contactos


def _extraer_contactos_para_creacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte campos planos de contacto en filas hijas y los remueve del payload del ORM padre."""
    resultado = dict(datos)
    contactos = _extraer_campos_contacto(resultado)
    for prefijo in _CONTACTOS_FORMULARIO.values():
        for atributo in _ATRIBUTOS_CONTACTO:
            resultado.pop(f"{prefijo}_{atributo}", None)
    if contactos:
        resultado["contactos"] = [
            ContactoFormulario(tipo=tipo, **valores)
            for tipo, valores in contactos.items()
        ]
    return resultado


def _extraer_relaciones_uno_a_uno_para_creacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte campos planos condicionales en sus tablas 1:1 de lenguaje de negocio."""
    resultado = dict(datos)

    datos_natural = {
        campo: resultado.pop(campo)
        for campo in _CAMPOS_PERSONA_NATURAL
        if campo in resultado
    }
    if datos_natural:
        resultado["datos_persona_natural"] = DatosPersonaNaturalFormulario(**datos_natural)

    clasificacion = {
        campo: resultado.pop(campo)
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA
        if campo in resultado
    }
    if clasificacion:
        resultado["clasificacion_tributaria"] = ClasificacionTributariaFormulario(**clasificacion)

    return resultado


def _aplicar_actualizacion_relaciones_uno_a_uno(orm: Formulario, campos: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica campos condicionales 1:1 y devuelve solo los campos que pertenecen a formularios."""
    restantes = dict(campos)

    datos_natural = {
        campo: restantes.pop(campo)
        for campo in _CAMPOS_PERSONA_NATURAL
        if campo in restantes
    }
    if datos_natural:
        if orm.datos_persona_natural is None:
            orm.datos_persona_natural = DatosPersonaNaturalFormulario()
        for campo, valor in datos_natural.items():
            setattr(orm.datos_persona_natural, campo, valor)

    clasificacion = {
        campo: restantes.pop(campo)
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA
        if campo in restantes
    }
    if clasificacion:
        if orm.clasificacion_tributaria is None:
            orm.clasificacion_tributaria = ClasificacionTributariaFormulario()
        for campo, valor in clasificacion.items():
            setattr(orm.clasificacion_tributaria, campo, valor)

    return restantes


def _tipo_persona_efectivo(orm: Optional[Formulario], datos: Dict[str, Any]) -> str:
    return str(datos.get("tipo_persona") or getattr(orm, "tipo_persona", "") or "").lower()


def _purgar_datos_no_aplicables_en_payload(datos: Dict[str, Any], orm: Optional[Formulario] = None) -> Dict[str, Any]:
    """
    Quita del payload los bloques que no corresponden al tipo de persona.
    Esta defensa vive en backend para que la integridad no dependa solo del UI.
    """
    resultado = dict(datos)
    tipo_persona = _tipo_persona_efectivo(orm, resultado)
    if tipo_persona == "natural":
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA:
            resultado.pop(campo, None)
        resultado["junta_directiva"] = []
        resultado["accionistas"] = []
        resultado["beneficiario_final"] = []
    elif tipo_persona == "juridica":
        for campo in _CAMPOS_PERSONA_NATURAL:
            resultado.pop(campo, None)
    return resultado


def _purgar_relaciones_no_aplicables(orm: Formulario, datos: Dict[str, Any]) -> None:
    tipo_persona = _tipo_persona_efectivo(orm, datos)
    if tipo_persona == "natural":
        orm.clasificacion_tributaria = None
        orm.junta_directiva = []
        orm.accionistas = []
        orm.beneficiario_final = []
    elif tipo_persona == "juridica":
        orm.datos_persona_natural = None


def _aplicar_actualizacion_contactos(orm: Formulario, campos: Dict[str, Any]) -> None:
    """Aplica cambios parciales de los 8 campos planos a la relación contactos."""
    contactos = _extraer_campos_contacto(campos)
    if not contactos:
        return

    existentes = {contacto.tipo: contacto for contacto in orm.contactos}
    for tipo, valores in contactos.items():
        contacto = existentes.get(tipo)
        if contacto is None:
            contacto = ContactoFormulario(tipo=tipo)
            orm.contactos.append(contacto)
        for atributo, valor in valores.items():
            setattr(contacto, atributo, valor)


def _contacto_por_tipo(orm: Formulario, tipo: str) -> Optional[ContactoFormulario]:
    for contacto in orm.contactos:
        if contacto.tipo == tipo:
            return contacto
    return None


def _valor_contacto(orm: Formulario, tipo: str, atributo: str) -> Optional[str]:
    contacto = _contacto_por_tipo(orm, tipo)
    return getattr(contacto, atributo) if contacto else None


def _deserializar_json(valor: Any) -> Any:
    """Convierte un JSON string almacenado en BD a su tipo Python (lista/dict)."""
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except (json.JSONDecodeError, TypeError):
            return valor
    return valor


def _serializar_json(valor: Any) -> Any:
    """Convierte listas/dicts Python a JSON string para almacenar en BD."""
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, default=_valor_json)
    return valor


def _valor_json(valor: Any) -> Any:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(f"Object of type {type(valor).__name__} is not JSON serializable")


def _aplicar_serializacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Serializa los campos JSON de un dict antes de persistirlo."""
    resultado = dict(datos)
    for campo in _CAMPOS_JSON:
        if campo in resultado:
            resultado[campo] = _serializar_json(resultado[campo])
    return resultado


def _normalizar_booleanos_no_nulos(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Evita NULL en columnas Boolean no nulas cuando un borrador envía campo vacío."""
    resultado = dict(datos)
    for campo in _CAMPOS_BOOLEANOS_SI_NO:
        if campo in resultado and resultado[campo] is None:
            resultado[campo] = False
    return resultado


def _normalizar_enum_str(valor: Optional[str]) -> str:
    """Convierte 'EnumClass.MEMBER' → 'member'. Sin efecto sobre valores ya correctos."""
    if not valor:
        return ""
    if "." in valor:
        return valor.rsplit(".", 1)[1].lower()
    return valor


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


class RepositorioFormularioSQLAlchemy:
    """Adaptador de persistencia para Formulario — usado por FormularioService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_por_id(self, formulario_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_por_codigo(self, codigo: str) -> Optional[FormularioDatos]:
        """Busca por codigo_peticion o por id. Carga relaciones para snapshot completo."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(
                (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
            )
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def crear(self, datos: Dict[str, Any]) -> FormularioDatos:
        """Persiste un nuevo formulario y retorna su representación de dominio."""
        datos_orm = _extraer_relaciones_uno_a_uno_para_creacion(
            _extraer_contactos_para_creacion(
                _construir_relaciones_dinamicas(
                    _normalizar_booleanos_no_nulos(_purgar_datos_no_aplicables_en_payload(datos))
                )
            )
        )
        orm = Formulario(**datos_orm)
        self._sesion.add(orm)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_formulario_a_datos(orm)

    def actualizar(self, formulario_id: str, campos: Dict[str, Any]) -> FormularioDatos:
        """Actualiza campos específicos y retorna la representación de dominio actualizada."""
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        if "estado" in campos:
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
        campos = _normalizar_booleanos_no_nulos(_purgar_datos_no_aplicables_en_payload(campos, orm))
        _purgar_relaciones_no_aplicables(orm, campos)
        _aplicar_actualizacion_contactos(orm, campos)
        campos_relacionales = _aplicar_actualizacion_relaciones_uno_a_uno(orm, campos)
        campos_orm = _extraer_contactos_para_creacion(_construir_relaciones_dinamicas(campos_relacionales))
        campos_orm.pop("contactos", None)
        for clave, valor in campos_orm.items():
            setattr(orm, clave, valor)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_formulario_a_datos(orm)

    def guardar_alertas(self, formulario_id: str, alertas: List[Dict[str, Any]]) -> None:
        """Guarda las alertas de inconsistencia ignoradas por el usuario al enviar."""
        self._sesion.query(AlertaInconsistencia).filter(
            AlertaInconsistencia.formulario_id == formulario_id
        ).delete()
        self._sesion.commit()

        if not alertas:
            return
        
        orms = [
            AlertaInconsistencia(formulario_id=formulario_id, **alerta)
            for alerta in alertas
        ]
        self._sesion.bulk_save_objects(orms)
        self._sesion.commit()

class RepositorioDocumentoSQLAlchemy:
    """Adaptador de persistencia para DocumentoAdjunto — usado por DocumentoService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def buscar(self, formulario_id: str, doc_id: str) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def listar_activos(self, formulario_id: str) -> List[DocumentoDatos]:
        orms = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .all()
        )
        return [_orm_documento_a_datos(o) for o in orms]

    def crear(self, datos: Dict[str, Any]) -> DocumentoDatos:
        """Persiste un nuevo documento adjunto y retorna su representación de dominio."""
        orm = DocumentoAdjunto(**_aplicar_serializacion(datos))
        self._sesion.add(orm)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_documento_a_datos(orm)

    def actualizar_rutas(self, rutas: Dict[str, str]) -> None:
        """Actualiza las rutas de archivo de varios documentos en una sola transacción."""
        for doc_id, nueva_ruta in rutas.items():
            self._sesion.query(DocumentoAdjunto).filter(
                DocumentoAdjunto.id == doc_id
            ).update({"ruta_archivo": nueva_ruta})
        self._sesion.commit()

    def marcar_eliminado(self, doc_id: str) -> None:
        """Soft-delete: registra la fecha de eliminación del documento."""
        self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id
        ).update({"deleted_at": datetime.now(timezone.utc)})
        self._sesion.commit()

    def actualizar_snapshot_datos(self, doc_id: str, snapshot_datos: str) -> None:
        """Actualiza la columna snapshot_datos de un documento específico."""
        self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id
        ).update({"snapshot_datos": snapshot_datos})
        self._sesion.commit()

    def obtener_ultimo_formulario_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]:
        """
        Retorna el PDF del formulario con el mayor version_numero activo.

        Se usa como ancla para construir la cadena de versiones al generar
        un nuevo PDF: el nuevo documento apuntará a este como version_anterior_id.
        """
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.version_numero.desc())
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None


class RepositorioValidacionSQLAlchemy:
    """Adaptador de persistencia para Formulario + ResultadoValidacion — usado por ValidacionService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .options(joinedload(Formulario.documentos))
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def limpiar_validaciones(self, formulario_id: str) -> None:
        self._sesion.query(ResultadoValidacion).filter(
            ResultadoValidacion.formulario_id == formulario_id
        ).delete()

    def guardar_validaciones(self, datos: List[Dict[str, Any]]) -> List[ResultadoValidacionDominio]:
        """Inserta todos los resultados de validación en una transacción y devuelve entidades de dominio."""
        orms = [ResultadoValidacion(**d) for d in datos]
        for orm in orms:
            self._sesion.add(orm)
        self._sesion.commit()
        for orm in orms:
            self._sesion.refresh(orm)
        return [_orm_validacion_a_dominio(orm) for orm in orms]


class RepositorioExpedienteSQLAlchemy:
    """Adaptador de persistencia para el portal interno — usado por ExpedienteService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def listar(
        self,
        estados: List[Any],
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> List[FormularioDatos]:
        consulta = self._sesion.query(Formulario).filter(
            Formulario.estado.in_(estados)
        )
        if contrapartes_permitidas is not None:
            consulta = consulta.filter(
                Formulario.tipo_contraparte.in_(contrapartes_permitidas)
            )
        if tipo_contraparte:
            consulta = consulta.filter(
                Formulario.tipo_contraparte == tipo_contraparte.lower()
            )
        if busqueda:
            termino = f"%{busqueda.strip()}%"
            consulta = consulta.filter(
                or_(
                    Formulario.razon_social.ilike(termino),
                    Formulario.codigo_peticion.ilike(termino),
                )
            )
        orms = consulta.order_by(Formulario.updated_at.desc()).all()
        return [_orm_formulario_a_datos(orm) for orm in orms]

    def obtener(self, formulario_id: str, estados: List[Any], bloquear: bool = False) -> Optional[FormularioDatos]:
        consulta = (
            self._sesion.query(Formulario)
            .filter(
                Formulario.id == formulario_id,
                Formulario.estado.in_(estados),
            )
        )
        if bloquear:
            consulta = consulta.with_for_update()
        orm = consulta.first()
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def buscar_documento_descargable(
        self, formulario_id: str, doc_id: str, estados: List[Any]
    ) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .join(Formulario, Formulario.id == DocumentoAdjunto.formulario_id)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
                Formulario.estado.in_(estados),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def listar_documentos(self, formulario_id: str) -> List[DocumentoDatos]:
        orms = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.created_at)
            .all()
        )
        return [_orm_documento_a_datos(orm) for orm in orms]

    def contar_documentos(self, ids_formularios: List[str]) -> Dict[str, int]:
        filas = (
            self._sesion.query(
                DocumentoAdjunto.formulario_id,
                func.count(DocumentoAdjunto.id).label("total"),
            )
            .filter(
                DocumentoAdjunto.formulario_id.in_(ids_formularios),
                DocumentoAdjunto.deleted_at.is_(None),
                DocumentoAdjunto.tipo_documento != TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
            )
            .group_by(DocumentoAdjunto.formulario_id)
            .all()
        )
        return {fila.formulario_id: fila.total for fila in filas}

    def actualizar_estado(self, formulario_id: str, estado: str) -> None:
        """Marca el nuevo estado en la sesión sin hacer commit.

        El commit lo realiza el caller (handler) después de registrar
        el evento de auditoría, garantizando que ambas operaciones sean
        atómicas en la misma transacción.
        """
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            # Informa al trigger de auditoría que este cambio viene de la aplicación.
            # SET LOCAL vive dentro de la transacción activa — no hace commit.
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.estado = estado
            # Sin commit aquí — el handler es responsable de confirmar la transacción.

    def actualizar_sagrilaft_reporte_id(self, formulario_id: str, reporte_id: str) -> None:
        """Persiste el ID del reporte de SAGRILAFT para descargas posteriores."""
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm and reporte_id:
            # Informa al trigger de auditoría que este cambio viene de la aplicación
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.sagrilaft_reporte_id = reporte_id
            self._sesion.commit()

    def actualizar_para_correccion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
        campos_a_corregir: str,
    ) -> None:
        """
        Persiste los campos de una devolución para corrección y hace commit.

        El commit de este método también confirma los cambios de AccesoManual
        pendientes en la misma sesión (AccesoManualService.reactivar_acceso_para_correccion
        modifica la sesión sin hacer commit, delegando aquí esa responsabilidad).
        """
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.estado = estado
            orm.numero_correccion = numero_correccion
            orm.campos_a_corregir = campos_a_corregir
            self._sesion.commit()

    def actualizar_para_deshacer_devolucion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
    ) -> None:
        """
        Revierte los campos de una devolución para corrección y hace commit.
        """
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.estado = estado
            orm.numero_correccion = numero_correccion
            orm.campos_a_corregir = None
            self._sesion.commit()

    def actualizar_para_reapertura_actualizacion(
        self,
        formulario_id: str,
        estado: str,
        campos_a_corregir: str,
    ) -> None:
        """
        Persiste la reapertura de una actualización y hace commit.

        El commit confirma también la reactivación del AccesoManual pendiente
        en la misma sesión.
        """
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.estado = estado
            orm.campos_a_corregir = campos_a_corregir
            # tipo_solicitud se preserva (vinculacion/actualizacion) — no se muta.
            # El tipo del ciclo actual queda en campos_a_corregir["tipo"] = ACTUALIZACION_REABIERTA.
            self._sesion.commit()

    def actualizar_estado_alerta(
        self,
        formulario_id: str,
        alerta_id: str,
        estado_auditoria: str,
        actor_id: str,
    ) -> None:
        self._sesion.query(AlertaInconsistencia).filter(
            AlertaInconsistencia.id == alerta_id,
            AlertaInconsistencia.formulario_id == formulario_id
        ).update({
            "estado_auditoria": estado_auditoria,
            "actualizado_por": actor_id,
        })
        self._sesion.commit()


class RepositorioFirmaSQLAlchemy:
    """Adaptador de persistencia para el flujo de firma — usado por FirmaService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str, bloquear: bool = False) -> Optional[FormularioDatos]:
        consulta = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
        )
        if bloquear:
            consulta = consulta.with_for_update()
        orm = consulta.first()
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_formulario_por_zoho_id(self, request_id: str, bloquear: bool = False) -> Optional[FormularioDatos]:
        consulta = (
            self._sesion.query(Formulario)
            .filter(Formulario.zoho_request_id == request_id)
        )
        if bloquear:
            consulta = consulta.with_for_update()
        orm = consulta.first()
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.version_numero.desc())
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def obtener_acceso_manual(self, formulario_id: str) -> Optional[AccesoManualDatos]:
        orm = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )
        return _orm_acceso_manual_a_datos(orm) if orm else None

    def obtener_certificado(self, formulario_id: str) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def crear_documento(self, datos: Dict[str, Any]) -> None:
        self._sesion.add(DocumentoAdjunto(**datos))
        self._sesion.commit()

    def actualizar_formulario(self, formulario_id: str, campos: Dict[str, Any]) -> None:
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            if "estado" in campos:
                self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            for campo, valor in campos.items():
                setattr(orm, campo, valor)
            self._sesion.commit()

    def actualizar_certificado(self, doc_id: str, ruta_archivo: str, tamano: int, hash_sha256: str) -> None:
        orm = self._sesion.query(DocumentoAdjunto).filter(DocumentoAdjunto.id == doc_id).first()
        if orm:
            orm.ruta_archivo = ruta_archivo
            orm.tamano = tamano
            orm.hash_sha256 = hash_sha256
            self._sesion.commit()


class RepositorioAccesoManualSQLAlchemy:
    """Adaptador de persistencia para accesos manuales — usado por AccesoManualService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_acceso_por_token(self, token: str) -> Optional[AccesoManualDatos]:
        orm = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(AccesoManual.token_diligenciamiento == token)
            .first()
        )
        return _orm_acceso_manual_a_datos(orm, con_formulario=True) if orm else None

    def obtener_acceso_por_formulario_id(
        self, formulario_id: str, *, cargar_formulario: bool = False
    ) -> Optional[AccesoManualDatos]:
        consulta = self._sesion.query(AccesoManual).filter(
            AccesoManual.formulario_id == formulario_id
        )
        if cargar_formulario:
            consulta = consulta.options(joinedload(AccesoManual.formulario))
        orm = consulta.first()
        return _orm_acceso_manual_a_datos(orm, con_formulario=cargar_formulario) if orm else None

    def obtener_formulario_por_codigo(self, codigo_peticion: str) -> Optional[FormularioDatos]:
        """Carga relaciones para que construir_snapshot_formulario funcione correctamente."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(Formulario.codigo_peticion == codigo_peticion)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def obtener_formulario_completo(self, formulario_id: str) -> Optional[FormularioDatos]:
        """Carga documentos y validaciones para construir el snapshot completo."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def listar_accesos(self) -> List[AccesoManualDatos]:
        orms = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .order_by(AccesoManual.created_at.desc())
            .all()
        )
        return [_orm_acceso_manual_a_datos(orm, con_formulario=True) for orm in orms]

    def crear_formulario_y_acceso(
        self,
        solicitud: SolicitudCreacionAcceso,
        pin_hash: str,
        token: str,
    ) -> ResultadoCreacionAcceso:
        """Crea el Formulario y el AccesoManual en una sola transacción."""
        from infrastructure.persistencia.models import generate_expires_at
        formulario = Formulario(
            tipo_contraparte=solicitud.tipo_contraparte,
            razon_social=solicitud.razon_social,
        )
        self._sesion.add(formulario)
        self._sesion.flush()  # genera formulario.id antes del acceso

        acceso = AccesoManual(
            pin_hash=pin_hash,
            token_diligenciamiento=token,
            correo_destinatario=solicitud.correo_destinatario,
            razon_social=solicitud.razon_social,
            tipo_contraparte=solicitud.tipo_contraparte,
            area_responsable=solicitud.area_responsable,
            formulario_id=formulario.id,
        )
        self._sesion.add(acceso)
        self._sesion.commit()
        self._sesion.refresh(formulario)
        self._sesion.refresh(acceso)

        return ResultadoCreacionAcceso(
            formulario_id=formulario.id,
            codigo_peticion=formulario.codigo_peticion,
            token_diligenciamiento=acceso.token_diligenciamiento,
            correo_destinatario=acceso.correo_destinatario,
            razon_social=acceso.razon_social,
            tipo_contraparte=acceso.tipo_contraparte or "",
            area_responsable=acceso.area_responsable or "",
            created_at=acceso.created_at,
            expires_at=acceso.expires_at,
        )

    def marcar_consumido(self, acceso_id: str, timestamp: datetime) -> None:
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.consumed_at = timestamp
            self._sesion.commit()

    def reactivar_acceso(
        self, acceso_id: str, nuevo_token: str, nuevo_expires_at: datetime
    ) -> None:
        """Actualiza el acceso sin commit — el caller (ExpedienteService) maneja la transacción."""
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.token_diligenciamiento = nuevo_token
            orm.consumed_at = None
            orm.expires_at = nuevo_expires_at

    def actualizar_correo_por_token(self, token: str, correo: str) -> None:
        """Actualiza el correo_destinatario del acceso asociado a un token."""
        acceso = self._sesion.query(AccesoManual).filter(AccesoManual.token_diligenciamiento == token).first()
        if acceso:
            acceso.correo_destinatario = correo
            self._sesion.commit()

    def obtener_acceso_activo_por_correo(self, correo: str) -> Optional[AccesoManualDatos]:
        """Obtiene el acceso más reciente que no esté consumido ni expirado para un correo."""
        from datetime import datetime, timezone
        ahora = datetime.now(timezone.utc)
        orm = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(
                AccesoManual.correo_destinatario == correo,
                AccesoManual.consumed_at.is_(None),
                AccesoManual.expires_at > ahora,
            )
            .order_by(AccesoManual.created_at.desc())
            .first()
        )
        return _orm_acceso_manual_a_datos(orm, con_formulario=True) if orm else None

    def reenviar_acceso(self, acceso_id: str, nuevo_pin_hash: str, nuevo_token: str, timestamp: datetime) -> None:
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.pin_hash = nuevo_pin_hash
            orm.token_diligenciamiento = nuevo_token
            orm.ultimo_envio_correo = timestamp
            self._sesion.commit()
