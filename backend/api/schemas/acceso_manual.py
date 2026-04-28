from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer

from infrastructure.persistencia.models import AreaResponsable, TipoContraparte

from .comunes import a_iso_utc


class SolicitudAccesoManual(BaseModel):
    """Datos para generar un acceso manual al formulario SAGRILAFT."""

    tipo_contraparte: TipoContraparte
    razon_social: str = Field(min_length=1, strip_whitespace=True)
    correo_destinatario: EmailStr
    area_responsable: AreaResponsable


class AccesoManualCreado(BaseModel):
    """
    Respuesta tras crear un acceso manual.

    Incluye el PIN en texto plano únicamente en este momento.
    """

    formulario_id: str
    codigo_peticion: str
    pin: str
    token_diligenciamiento: str
    enlace_diligenciamiento: str
    correo_destinatario: str
    razon_social: str
    tipo_contraparte: TipoContraparte
    area_responsable: AreaResponsable
    created_at: datetime
    expires_at: datetime

    @field_serializer("created_at", "expires_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class AccesoManualResumen(BaseModel):
    """Vista de listado sin PIN (nunca exponer el hash)."""

    id: str
    formulario_id: str
    codigo_peticion: str
    correo_destinatario: str
    razon_social: str
    tipo_contraparte: TipoContraparte
    area_responsable: AreaResponsable
    estado_acceso: Literal["activo", "consumido", "expirado"]
    created_at: datetime
    expires_at: datetime
    consumed_at: Optional[datetime] = None

    @field_serializer("created_at", "expires_at", "consumed_at", when_used="json")
    def _serializar_fechas(self, valor: Optional[datetime]) -> Optional[str]:
        return a_iso_utc(valor)


class CredencialesAccesoManual(BaseModel):
    """Credenciales para recuperar un formulario generado por acceso manual."""

    codigo_peticion: str
    pin: str

