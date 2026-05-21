from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

from domain.formulario.tipos import EstadoFormulario, TipoContraparte, TipoPersona
from domain.catalogo_correcciones import validar_campos_identificados

from .comunes import a_iso_utc


class ExpedienteResumen(BaseModel):
    """Vista compacta de un formulario enviado, para listados en el portal interno."""

    formulario_id: str
    codigo_peticion: str
    razon_social: Optional[str] = None
    numero_identificacion: Optional[str] = None
    tipo_contraparte: Optional[TipoContraparte] = None
    tipo_persona: Optional[TipoPersona] = None
    estado: EstadoFormulario
    cantidad_documentos: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class DocumentoResumen(BaseModel):
    """Metadatos mínimos de un documento adjunto para descarga desde el portal."""

    id: str
    tipo_documento: str
    nombre_archivo: str
    tamano: Optional[int] = None


class ExpedienteDetalle(BaseModel):
    """
    Vista de detalle de un expediente para el portal interno.

    Expone únicamente los campos que la pantalla necesita.
    Los datos del formulario (financieros, tributarios, representante legal, etc.)
    no se incluyen — están disponibles exclusivamente en el PDF descargable.
    """

    formulario_id: str
    codigo_peticion: str
    razon_social: Optional[str] = None
    tipo_contraparte: Optional[TipoContraparte] = None
    estado: EstadoFormulario
    updated_at: datetime
    documentos: List[DocumentoResumen] = []

    @field_serializer("updated_at", when_used="json")
    def _serializar_fecha(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class SolicitudDevolucion(BaseModel):
    """Datos requeridos para devolver un formulario al remitente para corrección."""

    especificaciones: str = Field(
        min_length=20,
        max_length=2000,
        description=(
            "Descripción exacta de qué información debe corregirse o completarse. "
            "Este texto se incluye en el correo enviado al destinatario."
        ),
    )
    campos_identificados: List[str] = Field(
        default_factory=list,
        description=(
            "IDs de los campos específicos del formulario que requieren corrección. "
            "Deben corresponder a identificadores del catálogo de campos del formulario."
        ),
    )

    @field_validator("campos_identificados")
    @classmethod
    def _validar_campos(cls, v: List[str]) -> List[str]:
        return validar_campos_identificados(v)


class ResumenDevolucion(BaseModel):
    """Resultado de una operación de devolución de formulario."""

    estado:            str
    correo_notificado: Optional[str] = None
    correo_enviado:    bool = False
