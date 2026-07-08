from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from domain.formulario.tipos import (
    ActividadClasificacion,
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
from domain.utils.coercion import (
    limpiar_numero_id_si_tipo_ausente,
    limpiar_vinculos_pep_si_no_es_pep,
)


class ErrorValidacion(BaseModel):
    campo: str
    mensaje: str

from .comunes import (
    BooleanoFormulario,
    DropdownSiNo,
    DropdownTipoId,
    EnumLimpio,
    FechaFormulario,
    MontoPositivo,
    PorcentajeParticipacion,
    a_iso_utc,
)
from .documentos import DocumentoResponse
from .validaciones import ValidacionResponse

SectorEmpresaLimpio = EnumLimpio[SectorEmpresa]
ResponsabilidadRentaLimpio = EnumLimpio[ResponsabilidadRenta]
ResponsabilidadIvaLimpio = EnumLimpio[ResponsabilidadIva]
RegimenIvaLimpio = EnumLimpio[RegimenIva]


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
        data = limpiar_numero_id_si_tipo_ausente(data)
        data = limpiar_vinculos_pep_si_no_es_pep(data)
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
    pais: Optional[str] = None
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
    fecha_expedicion: FechaFormulario = None
    ciudad_expedicion: Optional[str] = None
    nacionalidad: Optional[str] = None
    fecha_nacimiento: FechaFormulario = None
    ciudad_nacimiento: Optional[str] = None
    profesion: Optional[str] = None
    correo_representante: Optional[str] = None
    telefono_representante: Optional[str] = None
    direccion_funciones: Optional[str] = None
    pais_funciones: Optional[str] = None
    departamento_funciones: Optional[str] = None
    ciudad_funciones: Optional[str] = None
    direccion_residencia: Optional[str] = None
    ciudad_residencia: Optional[str] = None

    # 5. Información Financiera
    moneda_declaracion: Optional[str] = Field(None, description="Moneda en la que se declaran los valores financieros")
    moneda_declaracion_otra: Optional[str] = Field(None, description="Nombre de la moneda cuando moneda_declaracion es 'OTRA'")
    actividad_economica: Optional[str] = None
    codigo_ciiu: Optional[str] = None
    ingresos_mensuales: MontoPositivo = None
    otros_ingresos: MontoPositivo = None
    egresos_mensuales: MontoPositivo = None
    total_activos: MontoPositivo = None
    total_pasivos: MontoPositivo = None
    patrimonio: MontoPositivo = None

    # 6. Operaciones en Moneda Extranjera
    realiza_operaciones_moneda_extranjera: BooleanoFormulario = None
    paises_operaciones: Optional[str] = None
    tipos_transaccion: Optional[List[str]] = None
    tipos_transaccion_otros: Optional[str] = None

    # 8. Clasificación Empresa y Régimen Tributario
    actividad_clasificacion: EnumLimpio[ActividadClasificacion] = None
    actividad_especifica: Optional[str] = None
    sector: SectorEmpresaLimpio = None
    superintendencia: Optional[str] = None
    responsabilidades_renta: ResponsabilidadRentaLimpio = None
    autorretenedor: BooleanoFormulario = None
    responsabilidades_iva: ResponsabilidadIvaLimpio = None
    regimen_iva: RegimenIvaLimpio = None
    gran_contribuyente: BooleanoFormulario = None
    entidad_sin_animo_lucro: BooleanoFormulario = None
    retencion_ica: BooleanoFormulario = None
    impuesto_ica: BooleanoFormulario = None
    entidad_oficial: BooleanoFormulario = None
    exento_retencion_fuente: BooleanoFormulario = None

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
    dia_firma:    Optional[int] = None   # 1–31
    mes_firma:    Optional[int] = None   # 1–12
    year_firma:   Optional[int] = None   # ej: 2025
    ciudad_firma: Optional[str] = None

    # Datos dinámicos
    junta_directiva: Optional[List[MiembroJunta]] = None
    accionistas: Optional[List[Accionista]] = None
    beneficiario_final: Optional[List[BeneficiarioFinal]] = None
    referencias_comerciales: Optional[List[ReferenciaComercial]] = None
    referencias_bancarias: Optional[List[ReferenciaBancaria]] = None
    informacion_bancaria_pagos: Optional[List[InformacionBancariaPago]] = None

    # Metadata
    pagina_actual: Optional[int] = 1

    @field_validator("digito_verificacion")
    @classmethod
    def validar_digito_verificacion(cls, v: object) -> str | None:
        if v is None or v == "":
            return v
        # Normalizar: quitar espacios y saltos de línea (la IA puede retornarlos)
        limpio = str(v).strip()
        if not limpio:
            return None
        # Permitir explícitamente 'NA' enviado por el frontend cuando no es NIT
        if limpio.upper() == "NA":
            return "NA"
        # Algunos OCR devuelven "NIT-5" o "123456789-5": tomar el último dígito
        if len(limpio) > 1:
            ultimo = limpio[-1]
            if ultimo.isdigit():
                limpio = ultimo
        if len(limpio) != 1 or not limpio.isdigit():
            raise ValueError("El dígito de verificación debe ser un único dígito numérico (0-9)")
        return limpio

    @field_serializer(
        "ingresos_mensuales",
        "otros_ingresos",
        "egresos_mensuales",
        "total_activos",
        "total_pasivos",
        "patrimonio",
        when_used="json",
    )
    def _serializar_montos(self, valor: Decimal | None) -> float | None:
        return float(valor) if valor is not None else None

    @field_serializer("fecha_expedicion", "fecha_nacimiento", when_used="json")
    def _serializar_fechas_formulario(self, valor: date | None) -> str | None:
        return valor.isoformat() if valor else None


class FormularioCreate(FormularioBase):
    pass


class FormularioUpdate(FormularioBase):
    pass


class FormularioResponse(FormularioBase):
    id: str
    codigo_peticion: str
    estado: EstadoFormulario
    campos_a_corregir: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("created_at", "updated_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


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
