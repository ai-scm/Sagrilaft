import uuid
from datetime import datetime, timezone, timedelta
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


class ClasificacionActividad(str, enum.Enum):
    """
    Clasificación de la actividad comercial de la contraparte
    según su rol en la cadena de valor del sector regulado.
    """
    COMERCIALIZADOR       = "C"
    DISTRIBUIDOR          = "D"
    REPRESENTANTE         = "R"
    FABRICANTE            = "F"
    IMPORTADOR            = "I"


class ActividadClasificacion(str, enum.Enum):
    """
    Actividad principal de la empresa (Sección 8).
    """
    INDUSTRIAL         = "industrial"
    COMERCIAL          = "comercial"
    FINANCIERA         = "financiera"
    ECONOMIA_SOLIDARIA = "economia_solidaria"
    OTRA               = "otra"


class SectorEmpresa(str, enum.Enum):
    """
    Sector de la empresa (Sección 8).

    Valores canónicos: "Público", "Privado", "Mixto".
    """
    PUBLICO = "Público"
    PRIVADO = "Privado"
    MIXTO = "Mixto"


class ResponsabilidadRenta(str, enum.Enum):
    """
    Responsabilidad del contribuyente frente al impuesto sobre la renta (Sección 8).
    """
    DECLARANTE                  = "Declarante"
    NO_DECLARANTE               = "No declarante"
    DECLARANTE_REGIMEN_ESPECIAL = "Declarante Regimen Especial"


class ResponsabilidadIva(str, enum.Enum):
    """
    Responsabilidad del contribuyente frente al IVA (Sección 8).
    """
    RESPONSABLE    = "Responsable"
    NO_RESPONSABLE = "No responsable"

        
class RegimenIva(str, enum.Enum):
    """
    Régimen de IVA al que pertenece el contribuyente (Sección 8).
    """
    REGIMEN_COMUN        = "Régimen común"
    REGIMEN_SIMPLIFICADO = "Régimen simplificado"
    NINGUN_REGIMEN       = "Ningún régimen"

class AreaResponsable(str, enum.Enum):
    """
    Área interna responsable de gestionar el acceso manual al formulario SAGRILAFT.
    """
    VENTAS   = "ventas"
    LEGAL    = "legal"
    FINANZAS = "finanzas"


class OperacionesMonedaExtranjera(str, enum.Enum):
    """
    Operaciones en Moneda Extranjera - Seccion 6.
    """

    OPERACIONES_SI = "si"
    OPERACIONES_NO = "no"

class Autorretenedor(str, enum.Enum):
    """
    Indica si el contribuyente es autorretenedor (Paso 7).
    """
    AUTORRETENEDOR_SI = "si"
    AUTORRETENEDOR_NO = "no"

class GranContribuyente(str, enum.Enum):
    """
    Indica si el contribuyente es gran contribuyente (Paso 7).
    """
    GRAN_CONTRIBUYENTE_SI = "si"
    GRAN_CONTRIBUYENTE_NO = "no"

def generate_uuid():
    return str(uuid.uuid4())


def generate_codigo():
    return f"SAG-{uuid.uuid4().hex[:8].upper()}"


_DIAS_VIGENCIA_ACCESO = 30


def generate_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=_DIAS_VIGENCIA_ACCESO)


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
    realiza_operaciones_moneda_extranjera = Column(String, nullable=True)
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
    tipo_documento = Column(String, nullable=False)
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
    correo_destinatario = Column(String, nullable=False)
    razon_social = Column(String, nullable=False)
    tipo_contraparte = Column(String, nullable=False)
    area_responsable = Column(String, nullable=False)
    formulario_id = Column(String, ForeignKey("formularios.id"), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False, default=generate_expires_at)
    consumed_at = Column(DateTime, nullable=True)

    formulario = relationship("Formulario", foreign_keys=[formulario_id])
