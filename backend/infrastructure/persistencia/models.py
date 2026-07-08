import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Column, String, Integer, Float, Boolean, Text, DateTime, Numeric,
    Date, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from infrastructure.persistencia.database import Base
from domain.utils.fechas import sumar_dias_habiles, DIAS_HABILES_VIGENCIA_ACCESO

# Los enums de negocio viven en el dominio. Se re-exportan aquí para que
# todos los imports existentes (api/schemas, services) sigan funcionando
# sin cambios durante la migración incremental hacia arquitectura hexagonal.
from domain.formulario.tipos import (  # noqa: F401
    ActividadClasificacion,
    AreaResponsable,
    ClasificacionActividad,
    EstadoFormulario,
    RegimenIva,
    ResponsabilidadIva,
    ResponsabilidadRenta,
    SectorEmpresa,
    TipoContraparte,
    TipoPersona,
    TipoSolicitud,
)

def generate_uuid():
    return str(uuid.uuid4())


def generate_codigo():
    return f"SAG-{uuid.uuid4().hex[:8].upper()}"


def generate_expires_at() -> datetime:
    return sumar_dias_habiles(datetime.now(timezone.utc), DIAS_HABILES_VIGENCIA_ACCESO)


class Formulario(Base):
    __tablename__ = "formularios"

    id = Column(String, primary_key=True, default=generate_uuid)
    codigo_peticion = Column(String, unique=True, default=generate_codigo)
    estado = Column(String, default=EstadoFormulario.BORRADOR.value)
    pagina_actual = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # --- Clasificación ---
    tipo_contraparte         = Column(String, nullable=True)
    tipo_persona             = Column(String, nullable=True)
    tipo_solicitud           = Column(String, nullable=True)
    clasificacion_actividad  = Column(String, nullable=True)

    # --- 1. Información Básica Empresa ---
    razon_social = Column(String, nullable=True)
    tipo_identificacion = Column(String, nullable=True)
    numero_identificacion = Column(String, nullable=True)
    digito_verificacion = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    pais = Column(String, nullable=True)
    departamento = Column(String, nullable=True)
    ciudad = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    correo = Column(String, nullable=True)
    codigo_ica = Column(String, nullable=True)
    pagina_web = Column(String, nullable=True)

    # --- 2. Representante Legal ---
    nombre_representante = Column(String, nullable=True)
    tipo_doc_representante = Column(String, nullable=True)
    numero_doc_representante = Column(String, nullable=True)
    fecha_expedicion = Column(Date, nullable=True)
    ciudad_expedicion = Column(String, nullable=True)
    nacionalidad = Column(String, nullable=True)
    fecha_nacimiento = Column(Date, nullable=True)
    ciudad_nacimiento = Column(String, nullable=True)
    profesion = Column(String, nullable=True)
    correo_representante = Column(String, nullable=True)
    telefono_representante = Column(String, nullable=True)
    direccion_funciones = Column(String, nullable=True)
    pais_funciones = Column(String, nullable=True)
    departamento_funciones = Column(String, nullable=True)
    ciudad_funciones = Column(String, nullable=True)
    direccion_residencia = Column(String, nullable=True)
    ciudad_residencia = Column(String, nullable=True)

    # --- 5. Información Financiera ---
    moneda_declaracion = Column(String, nullable=True)
    moneda_declaracion_otra = Column(String, nullable=True)  # Especifica la moneda cuando moneda_declaracion == 'OTRA'
    actividad_economica = Column(String, nullable=True)
    codigo_ciiu = Column(String, nullable=True)
    ingresos_mensuales = Column(Numeric(18, 2), nullable=True)
    otros_ingresos = Column(Numeric(18, 2), nullable=True)
    egresos_mensuales = Column(Numeric(18, 2), nullable=True)
    total_activos = Column(Numeric(18, 2), nullable=True)
    total_pasivos = Column(Numeric(18, 2), nullable=True)
    patrimonio = Column(Numeric(18, 2), nullable=True)

    # --- 6. Operaciones en Moneda Extranjera ---
    realiza_operaciones_moneda_extranjera = Column(Boolean, nullable=False, default=False, server_default="false")
    paises_operaciones = Column(String, nullable=True)
    tipos_transaccion = Column(Text, nullable=True)    # JSON array ['importacion', ...]
    tipos_transaccion_otros = Column(String, nullable=True)

    # --- 8. Clasificación Empresa y Régimen Tributario ---
    actividad_clasificacion = Column(String, nullable=True)
    actividad_especifica = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    superintendencia = Column(String, nullable=True)
    responsabilidades_renta = Column(String, nullable=True)
    autorretenedor = Column(Boolean, nullable=False, default=False, server_default="false")
    responsabilidades_iva = Column(String, nullable=True)
    regimen_iva = Column(String, nullable=True)
    gran_contribuyente = Column(Boolean, nullable=False, default=False, server_default="false")
    entidad_sin_animo_lucro = Column(Boolean, nullable=False, default=False, server_default="false")
    retencion_ica = Column(Boolean, nullable=False, default=False, server_default="false")
    impuesto_ica = Column(Boolean, nullable=False, default=False, server_default="false")
    entidad_oficial = Column(Boolean, nullable=False, default=False, server_default="false")
    exento_retencion_fuente = Column(Boolean, nullable=False, default=False, server_default="false")

    # --- 11-12. Autorizaciones ---
    autorizacion_datos = Column(Boolean, default=False)
    declaracion_origen_fondos = Column(Boolean, default=False)
    origen_fondos = Column(Text, nullable=True)

    # --- 13. Firma ---
    dia_firma    = Column(Integer, nullable=True)   # 1–31
    mes_firma    = Column(Integer, nullable=True)   # 1–12
    year_firma   = Column(Integer, nullable=True)   # ej: 2025
    ciudad_firma = Column(String,  nullable=True)

    # --- Devolución para corrección ---
    campos_a_corregir  = Column(Text,    nullable=True)
    numero_correccion  = Column(Integer, nullable=False, default=0, server_default="0")

    # --- ZohoSign ---
    zoho_request_id        = Column(String, nullable=True)
    ruta_documento_firmado = Column(String, nullable=True)

    # Relaciones
    documentos = relationship("DocumentoAdjunto", back_populates="formulario",
                              cascade="all, delete-orphan",
                              primaryjoin="and_(Formulario.id==DocumentoAdjunto.formulario_id, DocumentoAdjunto.deleted_at.is_(None))")
    validaciones = relationship("ResultadoValidacion", back_populates="formulario",
                                cascade="all, delete-orphan")
    contactos = relationship("ContactoFormulario", back_populates="formulario",
                             cascade="all, delete-orphan", lazy="selectin")

    # --- Datos dinámicos (listas 1:N — Cambio 1 del rediseño de esquema) ---
    # lazy="selectin": evita N+1 en listados de expedientes (RepositorioExpedienteSQLAlchemy.listar),
    # que hoy recorren muchos formularios y acceden a estas 7 relaciones por cada uno.
    junta_directiva = relationship("MiembroJuntaDirectiva", back_populates="formulario",
                                   cascade="all, delete-orphan", order_by="MiembroJuntaDirectiva.orden",
                                   lazy="selectin")
    accionistas = relationship("AccionistaFormulario", back_populates="formulario",
                               cascade="all, delete-orphan", order_by="AccionistaFormulario.orden",
                               lazy="selectin")
    beneficiario_final = relationship("BeneficiarioFinalFormulario", back_populates="formulario",
                                      cascade="all, delete-orphan", order_by="BeneficiarioFinalFormulario.orden",
                                      lazy="selectin")
    referencias_comerciales = relationship("ReferenciaComercialFormulario", back_populates="formulario",
                                           cascade="all, delete-orphan", order_by="ReferenciaComercialFormulario.orden",
                                           lazy="selectin")
    referencias_bancarias = relationship("ReferenciaBancariaDeclarada", back_populates="formulario",
                                         cascade="all, delete-orphan", order_by="ReferenciaBancariaDeclarada.orden",
                                         lazy="selectin")
    informacion_bancaria_pagos = relationship("CuentaPagoFormulario", back_populates="formulario",
                                              cascade="all, delete-orphan", order_by="CuentaPagoFormulario.orden",
                                              lazy="selectin")
    tipos_transaccion = relationship("TipoTransaccionFormulario", back_populates="formulario",
                                     cascade="all, delete-orphan", lazy="selectin")


class MiembroJuntaDirectiva(Base):
    __tablename__ = "formulario_junta_directiva"
    __table_args__ = (
        Index("ix_formulario_junta_directiva_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    cargo = Column(String, nullable=True)
    nombre = Column(String, nullable=True)
    tipo_id = Column(String, nullable=True)
    numero_id = Column(String, nullable=True)
    es_pep = Column(String, nullable=True)
    vinculos_pep = Column(String, nullable=True)

    formulario = relationship("Formulario", back_populates="junta_directiva")


class AccionistaFormulario(Base):
    __tablename__ = "formulario_accionistas"
    __table_args__ = (
        Index("ix_formulario_accionistas_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    nombre = Column(String, nullable=True)
    tipo_id = Column(String, nullable=True)
    numero_id = Column(String, nullable=True)
    es_pep = Column(String, nullable=True)
    vinculos_pep = Column(String, nullable=True)
    porcentaje = Column(Float, nullable=True)

    formulario = relationship("Formulario", back_populates="accionistas")


class BeneficiarioFinalFormulario(Base):
    __tablename__ = "formulario_beneficiarios_finales"
    __table_args__ = (
        Index("ix_formulario_beneficiarios_finales_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    nombre = Column(String, nullable=True)
    tipo_id = Column(String, nullable=True)
    numero_id = Column(String, nullable=True)
    es_pep = Column(String, nullable=True)
    vinculos_pep = Column(String, nullable=True)
    porcentaje = Column(Float, nullable=True)

    formulario = relationship("Formulario", back_populates="beneficiario_final")


class ReferenciaComercialFormulario(Base):
    __tablename__ = "formulario_referencias_comerciales"
    __table_args__ = (
        Index("ix_formulario_referencias_comerciales_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    nombre_establecimiento = Column(String, nullable=True)
    persona_contacto = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    ciudad = Column(String, nullable=True)

    formulario = relationship("Formulario", back_populates="referencias_comerciales")


class ReferenciaBancariaDeclarada(Base):
    """Referencia bancaria declarada por la contraparte en el formulario (Paso 6).

    No confundir con `documentos_adjuntos.tipo_documento == 'referencias_bancarias'`,
    que es un certificado bancario adjunto con datos extraídos por IA — dominio distinto.
    """
    __tablename__ = "formulario_referencias_bancarias_declaradas"
    __table_args__ = (
        Index("ix_formulario_referencias_bancarias_declaradas_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    entidad = Column(String, nullable=True)
    producto = Column(String, nullable=True)

    formulario = relationship("Formulario", back_populates="referencias_bancarias")


class CuentaPagoFormulario(Base):
    __tablename__ = "formulario_cuentas_pago"
    __table_args__ = (
        Index("ix_formulario_cuentas_pago_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    entidad_bancaria = Column(String, nullable=True)
    ciudad_oficina = Column(String, nullable=True)
    tipo_cuenta = Column(String, nullable=True)
    numero_cuenta = Column(String, nullable=True)

    formulario = relationship("Formulario", back_populates="informacion_bancaria_pagos")


class TipoTransaccionFormulario(Base):
    """Multi-select de tipos de transacción en moneda extranjera (Paso 6).

    Tabla de unión simple: cada tag es un valor atómico, no una entidad con
    atributos propios (a diferencia de las demás tablas de este bloque).
    """
    __tablename__ = "formulario_tipos_transaccion"
    __table_args__ = (
        Index("ix_formulario_tipos_transaccion_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String, nullable=False)

    formulario = relationship("Formulario", back_populates="tipos_transaccion")


class ContactoFormulario(Base):
    __tablename__ = "contactos"
    __table_args__ = (
        UniqueConstraint("formulario_id", "tipo", name="uq_contactos_formulario_tipo"),
        Index("ix_contactos_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String, nullable=False)
    nombre = Column(String, nullable=True)
    cargo = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    correo = Column(String, nullable=True)

    formulario = relationship("Formulario", back_populates="contactos")


class DocumentoAdjunto(Base):
    __tablename__ = "documentos_adjuntos"
    __table_args__ = (
        Index("ix_documentos_adjuntos_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    tipo_documento = Column(String, nullable=False)
    nombre_archivo = Column(String, nullable=False)
    ruta_archivo = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    tamano = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Trazabilidad documental ────────────────────────────────────────────────
    version_numero = Column(Integer, nullable=False, default=1, server_default="1")
    version_anterior_id = Column(String, ForeignKey("documentos_adjuntos.id"), nullable=True)
    subido_por = Column(String(255), nullable=True)
    hash_sha256 = Column(String(64), nullable=True)
    snapshot_datos = Column(Text, nullable=True)

    formulario = relationship("Formulario", back_populates="documentos")


class ResultadoValidacion(Base):
    __tablename__ = "resultados_validacion"
    __table_args__ = (
        Index("ix_resultados_validacion_formulario_id", "formulario_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String, nullable=False)
    campo = Column(String, nullable=True)
    resultado = Column(String, nullable=False)
    detalle = Column(Text, nullable=True)
    valor_formulario = Column(String, nullable=True)
    valor_documento = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    formulario = relationship("Formulario", back_populates="validaciones")


class AccesoManual(Base):
    """
    Credenciales generadas por equipos internos para que clientes y proveedores
    accedan al formulario SAGRILAFT mediante un enlace tokenizado único.

    Invariantes:
    - formulario_id es único: un Formulario tiene a lo sumo un AccesoManual.
    - token_diligenciamiento es único: cada enlace apunta a un solo formulario.
    - pin_hash nunca almacena el PIN en texto plano (Argon2).
    """
    __tablename__ = "accesos_manuales"

    id = Column(String, primary_key=True, default=generate_uuid)
    pin_hash = Column(String, nullable=False)
    token_diligenciamiento = Column(String, unique=True, nullable=False)
    correo_destinatario = Column(String, nullable=True)
    razon_social = Column(String, nullable=False)
    tipo_contraparte = Column(String, nullable=False)
    area_responsable = Column(String, nullable=False)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False, default=generate_expires_at)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    formulario = relationship("Formulario", foreign_keys=[formulario_id])


class EventoFormulario(Base):
    """
    Log inmutable de eventos de ciclo de vida de un formulario SAGRILAFT.

    Cada fila representa una transición de estado o acción significativa.
    Nunca se actualizan — solo se insertan (append-only).
    """
    __tablename__ = "eventos_formulario"
    __table_args__ = (
        Index("ix_eventos_formulario_form_id", "formulario_id"),
        Index("ix_eventos_formulario_form_created", "formulario_id", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    formulario_id = Column(String, ForeignKey("formularios.id", ondelete="CASCADE"), nullable=False)
    tipo_evento = Column(String(60), nullable=False)
    estado_anterior = Column(String(50), nullable=True)
    estado_nuevo = Column(String(50), nullable=False)
    actor_id = Column(String(255), nullable=True)
    actor_tipo = Column(String(20), nullable=False, default="SISTEMA")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
