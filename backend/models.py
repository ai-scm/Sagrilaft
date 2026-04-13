import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class EstadoFormulario(str, enum.Enum):
    BORRADOR = "borrador"
    ENVIADO = "enviado"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"


class TipoPersona(str, enum.Enum):
    JURIDICA = "juridica"
    NATURAL = "natural"


class TipoContraparte(str, enum.Enum):
    PROVEEDOR = "proveedor"
    CLIENTE = "cliente"


class TipoSolicitud(str, enum.Enum):
    VINCULACION = "vinculacion"
    ACTUALIZACION = "actualizacion"


def generate_uuid():
    return str(uuid.uuid4())


def generate_codigo():
    return f"SAG-{uuid.uuid4().hex[:8].upper()}"


class Formulario(Base):
    __tablename__ = "formularios"

    id = Column(String, primary_key=True, default=generate_uuid)
    codigo_peticion = Column(String, unique=True, default=generate_codigo)
    estado = Column(String, default=EstadoFormulario.BORRADOR)
    pagina_actual = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # --- Clasificación ---
    tipo_contraparte = Column(String, nullable=True)
    tipo_persona = Column(String, nullable=True)
    tipo_solicitud = Column(String, nullable=True)

    # --- 1. Información Básica Empresa ---
    razon_social = Column(String, nullable=True)
    tipo_identificacion = Column(String, nullable=True)
    numero_identificacion = Column(String, nullable=True)
    digito_verificacion = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    pais = Column(String, default="Colombia")
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
    fecha_expedicion = Column(String, nullable=True)
    ciudad_expedicion = Column(String, nullable=True)
    nacionalidad = Column(String, nullable=True)
    fecha_nacimiento = Column(String, nullable=True)
    ciudad_nacimiento = Column(String, nullable=True)
    profesion = Column(String, nullable=True)
    correo_representante = Column(String, nullable=True)
    telefono_representante = Column(String, nullable=True)
    direccion_funciones = Column(String, nullable=True)
    ciudad_funciones = Column(String, nullable=True)
    direccion_residencia = Column(String, nullable=True)
    ciudad_residencia = Column(String, nullable=True)

    # --- 5. Información Financiera ---
    actividad_economica = Column(String, nullable=True)
    codigo_ciiu = Column(String, nullable=True)
    ingresos_mensuales = Column(Float, nullable=True)
    otros_ingresos = Column(Float, nullable=True)
    egresos_mensuales = Column(Float, nullable=True)
    total_activos = Column(Float, nullable=True)
    total_pasivos = Column(Float, nullable=True)
    patrimonio = Column(Float, nullable=True)

    # --- 6. Operaciones en Moneda Extranjera ---
    realiza_operaciones_moneda_extranjera = Column(String, nullable=True)  # 'si' | 'no'
    paises_operaciones = Column(String, nullable=True)
    tipos_transaccion = Column(Text, nullable=True)    # JSON array ['importacion', ...]
    tipos_transaccion_otros = Column(String, nullable=True)

    # --- 8. Clasificación Empresa y Régimen Tributario ---
    actividad_clasificacion = Column(String, nullable=True)
    actividad_especifica = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    superintendencia = Column(String, nullable=True)
    responsabilidades_renta = Column(String, nullable=True)
    autorretenedor = Column(String, nullable=True)
    responsabilidades_iva = Column(String, nullable=True)
    regimen_iva = Column(String, nullable=True)
    gran_contribuyente = Column(String, nullable=True)
    entidad_sin_animo_lucro = Column(String, nullable=True)
    retencion_ica = Column(String, nullable=True)
    impuesto_ica = Column(String, nullable=True)
    entidad_oficial = Column(String, nullable=True)
    exento_retencion_fuente = Column(String, nullable=True)

    # --- 9. Contactos ---
    contacto_ordenes_nombre = Column(String, nullable=True)
    contacto_ordenes_cargo = Column(String, nullable=True)
    contacto_ordenes_telefono = Column(String, nullable=True)
    contacto_ordenes_correo = Column(String, nullable=True)
    contacto_pagos_nombre = Column(String, nullable=True)
    contacto_pagos_cargo = Column(String, nullable=True)
    contacto_pagos_telefono = Column(String, nullable=True)
    contacto_pagos_correo = Column(String, nullable=True)

    # --- 11-12. Autorizaciones ---
    autorizacion_datos = Column(Boolean, default=False)
    declaracion_origen_fondos = Column(Boolean, default=False)
    origen_fondos = Column(Text, nullable=True)

    # --- 13. Firma ---
    fecha_firma = Column(String, nullable=True)
    ciudad_firma = Column(String, nullable=True)
    nombre_firma = Column(String, nullable=True)

    # --- Datos dinámicos (JSON) ---
    junta_directiva = Column(Text, nullable=True)              # JSON array
    accionistas = Column(Text, nullable=True)                   # JSON array
    beneficiario_final = Column(Text, nullable=True)            # JSON array
    referencias_comerciales = Column(Text, nullable=True)       # JSON array
    referencias_bancarias = Column(Text, nullable=True)         # JSON array
    informacion_bancaria_pagos = Column(Text, nullable=True)    # JSON array
    clasificaciones = Column(Text, nullable=True)               # JSON array

    # Relaciones
    documentos = relationship("DocumentoAdjunto", back_populates="formulario",
                              cascade="all, delete-orphan",
                              primaryjoin="and_(Formulario.id==DocumentoAdjunto.formulario_id, DocumentoAdjunto.deleted_at.is_(None))")
    validaciones = relationship("ResultadoValidacion", back_populates="formulario",
                                cascade="all, delete-orphan")


class DocumentoAdjunto(Base):
    __tablename__ = "documentos_adjuntos"

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id"), nullable=False)
    tipo_documento = Column(String, nullable=False)  # e.g. "cedula_representante", "rut", etc.
    nombre_archivo = Column(String, nullable=False)
    ruta_archivo = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    tamano = Column(Integer, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    formulario = relationship("Formulario", back_populates="documentos")


class ResultadoValidacion(Base):
    __tablename__ = "resultados_validacion"

    id = Column(String, primary_key=True, default=generate_uuid)
    formulario_id = Column(String, ForeignKey("formularios.id"), nullable=False)
    tipo = Column(String, nullable=False)  # "documento", "lista_cautela", "financiero"
    campo = Column(String, nullable=True)
    resultado = Column(String, nullable=False)  # "ok", "error", "advertencia"
    detalle = Column(Text, nullable=True)
    valor_formulario = Column(String, nullable=True)
    valor_documento = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    formulario = relationship("Formulario", back_populates="validaciones")
