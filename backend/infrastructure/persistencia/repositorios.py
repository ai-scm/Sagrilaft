"""
Implementaciones SQLAlchemy de los puertos de repositorio definidos en domain/puertos/.

Cada clase encapsula las operaciones de base de datos de un servicio específico,
eliminando el acoplamiento directo de los servicios a SQLAlchemy Session.

Todas las instancias de una misma solicitud HTTP comparten la misma Session
(FastAPI cachea Depends(get_db) por request), preservando la atomicidad
transaccional entre servicios.
"""

import json
from datetime import datetime, timezone
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
    DocumentoAdjunto,
    Formulario,
    ResultadoValidacion,
)

# Campos que se almacenan como JSON string en la base de datos.
# Deben serializarse al escribir y deserializarse al leer.
_CAMPOS_JSON = [
    "junta_directiva", "accionistas", "beneficiario_final",
    "referencias_comerciales", "referencias_bancarias",
    "informacion_bancaria_pagos", "clasificaciones", "tipos_transaccion",
    "snapshot_datos",
]


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
        return json.dumps(valor, ensure_ascii=False)
    return valor


def _aplicar_serializacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Serializa los campos JSON de un dict antes de persistirlo."""
    resultado = dict(datos)
    for campo in _CAMPOS_JSON:
        if campo in resultado:
            resultado[campo] = _serializar_json(resultado[campo])
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
        tipos_transaccion=_deserializar_json(orm.tipos_transaccion),
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
        contacto_ordenes_nombre=orm.contacto_ordenes_nombre,
        contacto_ordenes_cargo=orm.contacto_ordenes_cargo,
        contacto_ordenes_telefono=orm.contacto_ordenes_telefono,
        contacto_ordenes_correo=orm.contacto_ordenes_correo,
        contacto_pagos_nombre=orm.contacto_pagos_nombre,
        contacto_pagos_cargo=orm.contacto_pagos_cargo,
        contacto_pagos_telefono=orm.contacto_pagos_telefono,
        contacto_pagos_correo=orm.contacto_pagos_correo,
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
        junta_directiva=_deserializar_json(orm.junta_directiva),
        accionistas=_deserializar_json(orm.accionistas),
        beneficiario_final=_deserializar_json(orm.beneficiario_final),
        referencias_comerciales=_deserializar_json(orm.referencias_comerciales),
        referencias_bancarias=_deserializar_json(orm.referencias_bancarias),
        informacion_bancaria_pagos=_deserializar_json(orm.informacion_bancaria_pagos),
        clasificaciones=_deserializar_json(orm.clasificaciones),
        documentos=documentos,
        validaciones=validaciones,
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
        orm = Formulario(**_aplicar_serializacion(datos))
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
        for clave, valor in _aplicar_serializacion(campos).items():
            setattr(orm, clave, valor)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_formulario_a_datos(orm)


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

    def obtener(self, formulario_id: str, estados: List[Any]) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .filter(
                Formulario.id == formulario_id,
                Formulario.estado.in_(estados),
            )
            .first()
        )
        return _orm_formulario_a_datos(orm) if orm else None

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
        """Persiste el nuevo estado y hace commit inmediato."""
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            # Informa al trigger de auditoría que este cambio viene de la aplicación
            self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))
            orm.estado = estado
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
            self._sesion.commit()


class RepositorioFirmaSQLAlchemy:
    """Adaptador de persistencia para el flujo de firma — usado por FirmaService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_formulario_por_zoho_id(self, request_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.zoho_request_id == request_id)
            .first()
        )
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

    def actualizar_ruta_certificado(self, doc_id: str, ruta_archivo: str) -> None:
        orm = self._sesion.query(DocumentoAdjunto).filter(DocumentoAdjunto.id == doc_id).first()
        if orm:
            orm.ruta_archivo = ruta_archivo
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
