from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer

from domain.formulario.tipos import AreaResponsable, TipoContraparte

from .comunes import a_iso_utc


class SolicitudAccesoManual(BaseModel):
    """Datos para generar un acceso manual al formulario SAGRILAFT."""

    tipo_contraparte: TipoContraparte
    razon_social: str = Field(min_length=1, strip_whitespace=True)
    area_responsable: AreaResponsable
    correo_destinatario: Optional[EmailStr] = None


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
    razon_social: str
    tipo_contraparte: TipoContraparte
    area_responsable: AreaResponsable
    created_at: datetime
    expires_at: datetime
    correo_destinatario: Optional[str] = None
    correo_enviado: bool = False

    @field_serializer("created_at", "expires_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class AccesoManualResumen(BaseModel):
    """Vista de listado sin PIN (nunca exponer el hash)."""

    id: str
    formulario_id: str
    codigo_peticion: str
    razon_social: str
    tipo_contraparte: TipoContraparte
    area_responsable: AreaResponsable
    estado_acceso: Literal["activo", "consumido", "expirado"]
    created_at: datetime
    expires_at: datetime
    consumed_at: Optional[datetime] = None
    correo_destinatario: Optional[str] = None

    @field_serializer("created_at", "expires_at", "consumed_at", when_used="json")
    def _serializar_fechas(self, valor: Optional[datetime]) -> Optional[str]:
        return a_iso_utc(valor)


class CredencialesAccesoManual(BaseModel):
    """Credenciales para recuperar un formulario generado por acceso manual."""

    codigo_peticion: str
    pin: str


class ActualizarCorreoAcceso(BaseModel):
    """Datos para actualizar el correo de un acceso manual vía token."""

    correo_destinatario: EmailStr


class EstadoCorreoAcceso(BaseModel):
    """
    Respuesta liviana para verificar si el destinatario ya registró su correo.

    Se usa exclusivamente por el frontend al cargar la página para decidir si
    debe mostrar el modal de captura de correo. No expone datos del formulario.
    """

    correo_registrado: bool
