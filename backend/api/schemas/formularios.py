from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from infrastructure.persistencia.models import (
    ActividadClasificacion,
    Autorretenedor,
    ClasificacionActividad,
    EstadoFormulario,
    GranContribuyente,
    OperacionesMonedaExtranjera,
    RegimenIva,
    ResponsabilidadIva,
    ResponsabilidadRenta,
    SectorEmpresa,
    TipoContraparte,
    TipoPersona,
    TipoSolicitud,
)
from services.formulario.validacion_envio import (
    ErrorValidacion,
    _limpiar_numero_id_si_tipo_ausente,
    _limpiar_vinculos_pep_si_no_es_pep,
)

from .comunes import (
    DropdownSiNo,
    DropdownTipoId,
    EnumLimpio,
    MontoPositivo,
    PorcentajeParticipacion,
)
from .documentos import DocumentoResponse
from .validaciones import ValidacionResponse

SectorEmpresaLimpio = EnumLimpio[SectorEmpresa]
ResponsabilidadRentaLimpio = EnumLimpio[ResponsabilidadRenta]
ResponsabilidadIvaLimpio = EnumLimpio[ResponsabilidadIva]
RegimenIvaLimpio = EnumLimpio[RegimenIva]
OperacionesMonedaExtranjeraLimpio = EnumLimpio[OperacionesMonedaExtranjera]
AutorretenedorLimpio = EnumLimpio[Autorretenedor]
GranContribuyenteLimpio = EnumLimpio[GranContribuyente]


class PersonaVinculadaBase(BaseModel):
    """
    Entidad dinámica vinculada a la empresa (junta, accionistas, beneficiarios).
    Centraliza identificación + gestión PEP.
    """

    nombre: Optional[str] = None
    tipo_id: DropdownTipoId = None
    numero_id: Optional[str] = None
    es_pep: DropdownSiNo = None
    vinculos_pep: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validar_dependencias(cls, data: Any) -> Any:
        data = _limpiar_numero_id_si_tipo_ausente(data)
        data = _limpiar_vinculos_pep_si_no_es_pep(data)
        return data


class MiembroJunta(PersonaVinculadaBase):
    cargo: Optional[str] = None


class EntidadConParticipacion(PersonaVinculadaBase):
    porcentaje: PorcentajeParticipacion = None


class Accionista(EntidadConParticipacion):
    pass


class BeneficiarioFinal(EntidadConParticipacion):
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


class FormularioBase(BaseModel):
    # Clasificación
    tipo_contraparte: EnumLimpio[TipoContraparte] = None
    tipo_persona: EnumLimpio[TipoPersona] = None
    tipo_solicitud: EnumLimpio[TipoSolicitud] = None
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
    otros_ingresos: MontoPositivo = None
    egresos_mensuales: MontoPositivo = None
    total_activos: MontoPositivo = None
    total_pasivos: MontoPositivo = None
    patrimonio: MontoPositivo = None

    # 6. Operaciones en Moneda Extranjera
    realiza_operaciones_moneda_extranjera: EnumLimpio[OperacionesMonedaExtranjera] = None
    paises_operaciones: Optional[str] = None
    tipos_transaccion: Optional[List[str]] = None
    tipos_transaccion_otros: Optional[str] = None

    # 8. Clasificación Empresa y Régimen Tributario
    actividad_clasificacion: EnumLimpio[ActividadClasificacion] = None
    actividad_especifica: Optional[str] = None
    sector: SectorEmpresaLimpio = None
    superintendencia: Optional[str] = None
    responsabilidades_renta: ResponsabilidadRentaLimpio = None
    autorretenedor: EnumLimpio[Autorretenedor] = None
    responsabilidades_iva: ResponsabilidadIvaLimpio = None
    regimen_iva: RegimenIvaLimpio = None
    gran_contribuyente: EnumLimpio[GranContribuyente] = None
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

    @field_validator("digito_verificacion")
    @classmethod
    def validar_digito_verificacion(cls, v: object) -> str | None:
        if v is None or v == "":
            return v
        if len(str(v)) != 1 or not str(v).isdigit():
            raise ValueError("El dígito de verificación debe ser un único dígito numérico (0-9)")
        return str(v)

    @field_validator("retencion_ica", "impuesto_ica")
    @classmethod
    def validar_ica_si_no(cls, v: object) -> str | None:
        _valores_validos = {"si", "no"}
        if v is None or v == "":
            return None
        if v not in _valores_validos:
            raise ValueError("El valor de ICA debe ser estrictamente 'si' o 'no'")
        return str(v)


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
        "junta_directiva",
        "accionistas",
        "beneficiario_final",
        "referencias_comerciales",
        "referencias_bancarias",
        "informacion_bancaria_pagos",
        "clasificaciones",
        mode="before",
    )
    @classmethod
    def parse_json_strings(cls, v: object):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class FormularioConDetalles(FormularioResponse):
    documentos: List[DocumentoResponse] = Field(default_factory=list)
    validaciones: List[ValidacionResponse] = Field(default_factory=list)


class ResultadoValidacionEnvio(BaseModel):
    valido: bool
    errores: List[ErrorValidacion] = Field(default_factory=list)


class CredencialesEnvioFormulario(BaseModel):
    """
    Credenciales opcionales para radicar un formulario con acceso manual.

    Acepta token O código+PIN.
    """

    token_diligenciamiento: Optional[str] = None
    codigo_peticion: Optional[str] = None
    pin: Optional[str] = None

