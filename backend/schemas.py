import json

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime


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
    porcentaje: Optional[float] = None
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
    ingresos_mensuales: Optional[float] = None
    otros_ingresos: Optional[float] = None
    egresos_mensuales: Optional[float] = None
    total_activos: Optional[float] = None
    total_pasivos: Optional[float] = None
    patrimonio: Optional[float] = None

    # 7. Tipos de transacción
    tipos_transaccion: Optional[str] = None

    # 8. Clasificación Empresa
    actividad_clasificacion: Optional[str] = None
    actividad_especifica: Optional[str] = None
    sector: Optional[str] = None
    superintendencia: Optional[str] = None
    regimen_iva: Optional[str] = None
    gran_contribuyente: Optional[str] = None
    autorretenedor: Optional[bool] = False

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
    beneficiario_final: Optional[str] = None
    referencias_comerciales: Optional[List[ReferenciaComercial]] = None
    referencias_bancarias: Optional[List[ReferenciaBancaria]] = None
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
        "junta_directiva", "accionistas", "referencias_comerciales",
        "referencias_bancarias", "clasificaciones",
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


class DocumentoResponse(BaseModel):
    id: str
    tipo_documento: str
    nombre_archivo: str
    content_type: Optional[str] = None
    tamano: Optional[int] = None
    created_at: datetime
    # Presente solo en el response del upload, nulo en listados
    campos_sugeridos: Optional[dict] = None

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
    errores: List[ErrorValidacion] = []


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
