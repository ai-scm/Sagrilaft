import json

from pydantic import BaseModel, BeforeValidator, field_validator
from typing import Annotated, Optional, List
from datetime import datetime


# ── Tipos anotados para campos numéricos del formulario ──────────────────────

def _coercionar_monto(v: object) -> float | None:
    """
    Coerciona un valor de entrada (str o float) a float no negativo.
    Cadenas vacías y None se interpretan como ausencia de valor (None).
    Rechaza valores negativos ya que los montos financieros no pueden serlo.
    """
    if v is None or v == '':
        return None
    try:
        valor = float(v)
    except (TypeError, ValueError):
        raise ValueError('Debe ser un número válido')
    if valor < 0:
        raise ValueError('El monto no puede ser negativo')
    return valor


def _coercionar_porcentaje(v: object) -> float | None:
    """
    Coerciona un valor de entrada (str o float) a float en rango [0, 100].
    Cadenas vacías y None se interpretan como ausencia de valor (None).
    """
    if v is None or v == '':
        return None
    try:
        valor = float(v)
    except (TypeError, ValueError):
        raise ValueError('Debe ser un número válido entre 0 y 100')
    if valor < 0:
        raise ValueError('El porcentaje no puede ser negativo')
    if valor > 100:
        raise ValueError('El porcentaje no puede superar 100')
    return valor


def _coercionar_porcentaje_participacion(v: object) -> float | None:
    """
    Coerciona porcentaje de participación accionaria o control efectivo.
    Rango permitido: (0, 100) exclusivo — ningún titular puede ostentar el 100%,
    pues la figura aplica solo cuando existen múltiples partes.
    """
    valor = _coercionar_porcentaje(v)
    if valor is not None and valor >= 100:
        raise ValueError('El porcentaje de participación no puede ser igual o superior al 100%')
    return valor


# Tipos reutilizables en cualquier schema que maneje montos o porcentajes
MontoPositivo          = Annotated[Optional[float], BeforeValidator(_coercionar_monto)]
PorcentajeValido       = Annotated[Optional[float], BeforeValidator(_coercionar_porcentaje)]
PorcentajeParticipacion = Annotated[Optional[float], BeforeValidator(_coercionar_porcentaje_participacion)]


# --- Sub-schemas para datos dinámicos ---
class MiembroJunta(BaseModel):
    cargo: Optional[str] = None
    nombre: Optional[str] = None
    tipo_id: Optional[str] = None
    numero_id: Optional[str] = None
    es_pep: Optional[str] = None
    vinculos_pep: Optional[str] = None


class Accionista(BaseModel):
    nombre: Optional[str] = None
    porcentaje: PorcentajeParticipacion = None
    tipo_id: Optional[str] = None
    numero_id: Optional[str] = None
    es_pep: Optional[str] = None
    vinculos_pep: Optional[str] = None


class BeneficiarioFinal(BaseModel):
    nombre: Optional[str] = None
    porcentaje: PorcentajeParticipacion = None
    tipo_id: Optional[str] = None
    numero_id: Optional[str] = None
    es_pep: Optional[str] = None
    vinculos_pep: Optional[str] = None


class ReferenciaComercial(BaseModel):
    nombre: Optional[str] = None
    contacto: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None


class ReferenciaBancaria(BaseModel):
    entidad: Optional[str] = None
    producto: Optional[str] = None


class InformacionBancariaPago(BaseModel):
    entidad_bancaria: Optional[str] = None
    ciudad_oficina: Optional[str] = None
    tipo_cuenta: Optional[str] = None
    numero_cuenta: Optional[str] = None


# --- Schema principal del formulario ---
class FormularioBase(BaseModel):
    # Clasificación
    tipo_contraparte: Optional[str] = None
    tipo_persona: Optional[str] = None
    tipo_solicitud: Optional[str] = None

    # 1. Info Básica
    razon_social: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    direccion: Optional[str] = None
    pais: Optional[str] = "Colombia"
    departamento: Optional[str] = None
    ciudad: Optional[str] = None
    telefono: Optional[str] = None
    fax: Optional[str] = None
    correo: Optional[str] = None
    codigo_ica: Optional[str] = None
    pagina_web: Optional[str] = None

    # 2. Representante Legal
    nombre_representante: Optional[str] = None
    tipo_doc_representante: Optional[str] = None
    numero_doc_representante: Optional[str] = None
    fecha_expedicion: Optional[str] = None
    ciudad_expedicion: Optional[str] = None
    nacionalidad: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    ciudad_nacimiento: Optional[str] = None
    profesion: Optional[str] = None
    correo_representante: Optional[str] = None
    telefono_representante: Optional[str] = None
    direccion_funciones: Optional[str] = None
    ciudad_funciones: Optional[str] = None
    direccion_residencia: Optional[str] = None
    ciudad_residencia: Optional[str] = None

    # 5. Información Financiera
    actividad_economica: Optional[str] = None
    codigo_ciiu: Optional[str] = None
    ingresos_mensuales: MontoPositivo = None
    otros_ingresos:     MontoPositivo = None
    egresos_mensuales:  MontoPositivo = None
    total_activos:      MontoPositivo = None
    total_pasivos:      MontoPositivo = None
    patrimonio:         MontoPositivo = None

    # 7. Tipos de transacción
    tipos_transaccion: Optional[str] = None

    # 8. Clasificación Empresa y Régimen Tributario
    actividad_clasificacion: Optional[str] = None
    actividad_especifica: Optional[str] = None
    sector: Optional[str] = None
    superintendencia: Optional[str] = None
    responsabilidades_renta: Optional[str] = None
    autorretenedor: Optional[str] = None
    responsabilidades_iva: Optional[str] = None
    regimen_iva: Optional[str] = None
    gran_contribuyente: Optional[str] = None
    entidad_sin_animo_lucro: Optional[str] = None
    retencion_ica: Optional[str] = None
    impuesto_ica: Optional[str] = None
    entidad_oficial: Optional[str] = None
    exento_retencion_fuente: Optional[str] = None

    # 9. Contactos
    contacto_ordenes_nombre: Optional[str] = None
    contacto_ordenes_cargo: Optional[str] = None
    contacto_ordenes_telefono: Optional[str] = None
    contacto_ordenes_correo: Optional[str] = None
    contacto_pagos_nombre: Optional[str] = None
    contacto_pagos_cargo: Optional[str] = None
    contacto_pagos_telefono: Optional[str] = None
    contacto_pagos_correo: Optional[str] = None

    # 11-12. Autorizaciones
    autorizacion_datos: Optional[bool] = False
    declaracion_origen_fondos: Optional[bool] = False
    origen_fondos: Optional[str] = None

    # 13. Firma
    fecha_firma: Optional[str] = None
    ciudad_firma: Optional[str] = None
    nombre_firma: Optional[str] = None

    # Datos dinámicos
    junta_directiva: Optional[List[MiembroJunta]] = None
    accionistas: Optional[List[Accionista]] = None
    beneficiario_final: Optional[List[BeneficiarioFinal]] = None
    referencias_comerciales: Optional[List[ReferenciaComercial]] = None
    referencias_bancarias: Optional[List[ReferenciaBancaria]] = None
    informacion_bancaria_pagos: Optional[List[InformacionBancariaPago]] = None
    clasificaciones: Optional[List[str]] = None

    # Metadata
    pagina_actual: Optional[int] = 1


class FormularioCreate(FormularioBase):
    pass


class FormularioUpdate(FormularioBase):
    pass


class FormularioResponse(FormularioBase):
    id: str
    codigo_peticion: str
    estado: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator(
        "junta_directiva", "accionistas", "beneficiario_final",
        "referencias_comerciales", "referencias_bancarias",
        "informacion_bancaria_pagos", "clasificaciones",
        mode="before"
    )
    @classmethod
    def parse_json_strings(cls, v):
        """Convierte strings JSON de la BD en listas Python."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class AlertaInconsistenciaResponse(BaseModel):
    """
    Representa una inconsistencia detectada entre un campo del formulario
    y el valor encontrado en un documento adjunto.

    Schema HTTP unificado para todos los tipos de alerta de campo
    (nombre, NIT, nombre representante, número documento, dirección).
    Presente en DocumentoResponse únicamente cuando hay discrepancia.

    Attributes:
        tipo_documento:     Clave del tipo de documento (ej. "certificado_existencia").
        nombre_documento:   Nombre legible del documento para mostrar al usuario.
        seccion_referencia: Ubicación exacta del campo dentro del documento.
        valor_formulario:   Valor ingresado por el usuario en el formulario.
        valor_documento:    Valor extraído del documento por la IA.
        tipo_alerta:        Gravedad: "error" | "advertencia".
        mensaje:            Descripción legible para el usuario final.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str    # "error" | "advertencia"
    mensaje: str


class DocumentoResponse(BaseModel):
    id: str
    tipo_documento: str
    nombre_archivo: str
    content_type: Optional[str] = None
    tamano: Optional[int] = None
    created_at: datetime
    # Presentes solo en el response del upload, nulos en listados
    campos_sugeridos: Optional[dict] = None
    razon_social_extraida: Optional[str] = None
    alerta_nombre: Optional[AlertaInconsistenciaResponse] = None
    nit_extraido: Optional[str] = None
    alerta_nit: Optional[AlertaInconsistenciaResponse] = None
    nombre_representante_extraido: Optional[str] = None
    alerta_nombre_representante: Optional[AlertaInconsistenciaResponse] = None
    numero_doc_representante_extraido: Optional[str] = None
    alerta_numero_doc_representante: Optional[AlertaInconsistenciaResponse] = None
    direccion_extraida: Optional[str] = None
    alerta_direccion: Optional[AlertaInconsistenciaResponse] = None

    class Config:
        from_attributes = True


class ValidacionResponse(BaseModel):
    id: str
    tipo: str
    campo: Optional[str] = None
    resultado: str
    detalle: Optional[str] = None
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FormularioConDetalles(FormularioResponse):
    documentos: List[DocumentoResponse] = []
    validaciones: List[ValidacionResponse] = []


# --- Validación para envío final ---
class ErrorValidacion(BaseModel):
    campo: str
    mensaje: str


class ResultadoValidacionEnvio(BaseModel):
    valido: bool


# --- Listas de cautela ---
class BusquedaListaCautela(BaseModel):
    nombre: str
    numero_identificacion: Optional[str] = None


class ResultadoListaCautela(BaseModel):
    lista: str
    encontrado: bool
    detalle: Optional[str] = None
    nivel_riesgo: Optional[str] = None  # "bajo", "medio", "alto"


class RespuestaListaCautela(BaseModel):
    nombre_buscado: str
    resultados: List[ResultadoListaCautela] = []
    riesgo_general: str = "bajo"  # "bajo", "medio", "alto"
