from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer, model_validator
from typing import Optional, Any

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
    extraccion_exitosa: bool = False
    mensaje_extraccion: str = ""

    @field_serializer("created_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""

    @model_validator(mode="before")
    @classmethod
    def extract_snapshot_datos(cls, data: Any) -> Any:
        # If it's an ORM object or DocumentoDatos with snapshot_datos
        if hasattr(data, "snapshot_datos") and isinstance(data.snapshot_datos, dict):
            # We can't mutate data if it's an object, we just return it but Pydantic
            # reads from its attributes. Since we need to inject fields, it's better to
            # convert to dict if it's an object, or we can just let `from_attributes=True` work
            # by providing a wrapper or we can convert it to a dict.
            if hasattr(data, "model_dump"):
                d = data.model_dump()
            elif hasattr(data, "__dict__"):
                d = dict(data.__dict__)
            else:
                d = dict(data)
                
            for field in [
                "razon_social_extraida", "nit_extraido", "nombre_representante_extraido",
                "numero_doc_representante_extraido", "direccion_extraida", "extraccion_exitosa"
            ]:
                if field in data.snapshot_datos and not d.get(field):
                    d[field] = data.snapshot_datos[field]
            return d
        
        # If it's already a dict
        if isinstance(data, dict) and isinstance(data.get("snapshot_datos"), dict):
            for field in [
                "razon_social_extraida", "nit_extraido", "nombre_representante_extraido",
                "numero_doc_representante_extraido", "direccion_extraida", "extraccion_exitosa"
            ]:
                if field in data["snapshot_datos"] and not data.get(field):
                    data[field] = data["snapshot_datos"][field]
        return data

    class Config:
        from_attributes = True

