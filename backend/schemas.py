import json

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator
from typing import Annotated, Any, Optional, List, TypeVar, Literal
from datetime import datetime

from models import (
    ClasificacionActividad,
    EstadoFormulario,
    TipoContraparte,
    TipoPersona,
    TipoSolicitud,
    ActividadClasificacion,
    SectorEmpresa,
    ResponsabilidadRenta,
    ResponsabilidadIva,
    RegimenIva,
)

from services.utils.coercion import (
    coercionar_monto,
    coercionar_porcentaje,
    coercionar_porcentaje_participacion
)

from services.formulario.validacion import (
    _vacio_a_nulo,
    _limpiar_numero_id_si_tipo_ausente,
    _limpiar_vinculos_pep_si_no_es_pep,
    ErrorValidacion
)


# ── Validadores Transversales y Tipos Anotados ───────────────────────────────

T = TypeVar('T')


EnumLimpio = Annotated[Optional[T], BeforeValidator(_vacio_a_nulo)]

# Literales para estandarización estricta de Dropdowns fijos (sin enums complejos)
DropdownSiNo = Annotated[Literal['si', 'no'] | None, BeforeValidator(_vacio_a_nulo)]
DropdownTipoId = Annotated[Literal['NIT', 'CC', 'CE', 'PAS'] | None, BeforeValidator(_vacio_a_nulo)]

SectorEmpresaLimpio       = EnumLimpio[SectorEmpresa]
ResponsabilidadRentaLimpio = EnumLimpio[ResponsabilidadRenta]
ResponsabilidadIvaLimpio   = EnumLimpio[ResponsabilidadIva]
RegimenIvaLimpio           = EnumLimpio[RegimenIva]


# Tipos reutilizables en cualquier schema que maneje montos o porcentajes
MontoPositivo          = Annotated[Optional[float], BeforeValidator(coercionar_monto)]
PorcentajeValido       = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje)]
PorcentajeParticipacion = Annotated[Optional[float], BeforeValidator(coercionar_porcentaje_participacion)]


# --- Sub-schemas para datos dinámicos ---



class PersonaVinculadaBase(BaseModel):
    """
    Clase base para entidades dinámicas vinculadas a la empresa (Secciones Junta, Accionistas, Beneficiarios).
    Centraliza los campos compartidos de identificación y gestión PEP y sus lógicas de dependencia.
    """
    nombre: Optional[str] = None
    tipo_id: DropdownTipoId = None
    numero_id: Optional[str] = None
    es_pep: DropdownSiNo = None
    vinculos_pep: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def validar_dependencias(cls, data: Any) -> Any:
        data = _limpiar_numero_id_si_tipo_ausente(data)
        data = _limpiar_vinculos_pep_si_no_es_pep(data)
        return data


class MiembroJunta(PersonaVinculadaBase):
    """ Hereda nombre, id, pep y agrega campo específico: cargo """
    cargo: Optional[str] = None


class EntidadConParticipacion(PersonaVinculadaBase):
    """
    Clase intermedia para entidades que poseen un porcentaje de participación o control.
    """
    porcentaje: PorcentajeParticipacion = None


class Accionista(EntidadConParticipacion):
    """ Hereda nombre, id, pep y porcentaje de participación """
    pass


class BeneficiarioFinal(EntidadConParticipacion):
    """ Idéntico estructuralmente a un Accionista, diferenciable en el dominio del negocio """
    pass


class ReferenciaComercial(BaseModel):
    nombre_establecimiento: Optional[str] = None
    persona_contacto: Optional[str] = None
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
    tipo_contraparte:        EnumLimpio[TipoContraparte] = None
    tipo_persona:            EnumLimpio[TipoPersona] = None
    tipo_solicitud:          EnumLimpio[TipoSolicitud] = None
    clasificacion_actividad: EnumLimpio[ClasificacionActividad] = None

    # 1. Info Básica
    razon_social: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    digito_verificacion: Optional[str] = None
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

    # 6. Operaciones en Moneda Extranjera
    realiza_operaciones_moneda_extranjera: Optional[str] = None
    paises_operaciones: Optional[str] = None
    tipos_transaccion: Optional[List[str]] = None
    tipos_transaccion_otros: Optional[str] = None

    # 8. Clasificación Empresa y Régimen Tributario
    actividad_clasificacion: EnumLimpio[ActividadClasificacion] = None
    actividad_especifica: Optional[str] = None
    sector: SectorEmpresaLimpio = None
    superintendencia: Optional[str] = None
    responsabilidades_renta: ResponsabilidadRentaLimpio = None
    autorretenedor: Optional[str] = None
    responsabilidades_iva: ResponsabilidadIvaLimpio = None
    regimen_iva: RegimenIvaLimpio = None
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

    @field_validator('digito_verificacion')
    @classmethod
    def validar_digito_verificacion(cls, v: object) -> str | None:
        """El DV debe ser un único dígito numérico (0-9). Cadenas vacías se tratan como ausencia."""
        if v is None or v == '':
            return v
        if len(str(v)) != 1 or not str(v).isdigit():
            raise ValueError('El dígito de verificación debe ser un único dígito numérico (0-9)')
        return str(v)

    @field_validator('realiza_operaciones_moneda_extranjera')
    @classmethod
    def validar_realiza_operaciones_moneda_extranjera(cls, v: object) -> str | None:
        """Solo se aceptan los valores 'si' o 'no'. Cadenas vacías se tratan como ausencia."""
        _VALORES_VALIDOS = {'si', 'no'}
        if v is None or v == '':
            return None
        if str(v).lower() not in _VALORES_VALIDOS:
            raise ValueError("El valor debe ser 'si' o 'no'")
        return str(v).lower()

    @field_validator('retencion_ica', 'impuesto_ica')
    @classmethod
    def validar_ica_si_no(cls, v: object) -> str | None:
        """
        Los campos de ICA retención e impuesto sólo admiten valores booleanos
        estructurados como string desde el dropdown del frontend ('si', 'no').
        La validación es estricta.
        """
        _VALORES_VALIDOS = {'si', 'no'}
        if v is None or v == '':
            return None
            
        if v not in _VALORES_VALIDOS:
            raise ValueError("El valor de ICA debe ser estrictamente 'si' o 'no'")
            
        return v


class FormularioCreate(FormularioBase):
    pass


class FormularioUpdate(FormularioBase):
    pass


class FormularioResponse(FormularioBase):
    id: str
    codigo_peticion: str
    estado: EstadoFormulario
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
    documentos: List[DocumentoResponse] = Field(default_factory=list)
    validaciones: List[ValidacionResponse] = Field(default_factory=list)




class ResultadoValidacionEnvio(BaseModel):
    valido: bool
    errores: List[ErrorValidacion] = Field(default_factory=list)


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
    resultados: List[ResultadoListaCautela] = Field(default_factory=list)
    riesgo_general: str = "bajo"  # "bajo", "medio", "alto"


# --- Recuperación de sesión por credenciales ---

class CredencialesRecuperacion(BaseModel):
    """
    Credenciales que identifican unívocamente al usuario para recuperar
    un borrador activo desde cualquier dispositivo.

    Reemplaza el flujo anterior basado en el código SAG- como identificador
    expuesto al usuario. El código se mantiene internamente en la BD.
    """

    correo: str
    numero_identificacion: str
