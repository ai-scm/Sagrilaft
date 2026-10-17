"""
DTOs de creación y snapshot de acceso manual al formulario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AccesoManualDatos:
    """Snapshot completo de un AccesoManual — campos para firma y acceso."""
    id: str
    formulario_id: str
    razon_social: str
    correo_destinatario: str
    # Campos extendidos — default vacío para compatibilidad con usos parciales (FirmaService)
    tipo_contraparte: str = ""
    area_responsable: str = ""
    pin_hash: str = ""
    token_diligenciamiento: str = ""
    consumed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    ultimo_envio_correo: Optional[datetime] = None
    estado_formulario: str = ""
    codigo_peticion: str = ""


@dataclass
class SolicitudCreacionAcceso:
    """DTO de entrada para crear un acceso manual al formulario SAGRILAFT."""
    tipo_contraparte: str
    razon_social: str
    area_responsable: str
    correo_destinatario: str


@dataclass
class ResultadoCreacionAcceso:
    """Datos retornados tras crear formulario + acceso manual en un solo paso."""
    formulario_id: str
    codigo_peticion: str
    token_diligenciamiento: str
    razon_social: str
    tipo_contraparte: str
    area_responsable: str
    created_at: datetime
    expires_at: datetime
    correo_destinatario: str
