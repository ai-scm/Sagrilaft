from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer

from .comunes import a_iso_utc


class AlertaInconsistenciaResponse(BaseModel):
    """
    Inconsistencia detectada entre un campo del formulario y un documento adjunto.

    Schema HTTP unificado para todos los tipos de alerta de campo.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str  # "error" | "advertencia"
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

    @field_serializer("created_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""

    class Config:
        from_attributes = True

