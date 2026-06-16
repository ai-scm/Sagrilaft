"""
Entidades y tipos de dominio para trazabilidad y auditoría.

Sin ORM, sin HTTP — solo tipos Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


class TipoEvento:
    """Constantes de tipos de evento del ciclo de vida de un formulario."""

    # ── Ciclo de vida del formulario ──────────────────────────────────────────
    FORMULARIO_CREADO    = "FORMULARIO_CREADO"
    FORMULARIO_ENVIADO   = "FORMULARIO_ENVIADO"
    FORMULARIO_APROBADO  = "FORMULARIO_APROBADO"
    FORMULARIO_RECHAZADO = "FORMULARIO_RECHAZADO"
    FORMULARIO_DEVUELTO  = "FORMULARIO_DEVUELTO"
    FORMULARIO_CARGADO_MANUALMENTE = "FORMULARIO_CARGADO_MANUALMENTE"
    REPORTE_FINAL_CARGADO = "REPORTE_FINAL_CARGADO"
    REPORTE_FINAL_ELIMINADO = "REPORTE_FINAL_ELIMINADO"

    # ── Firma electrónica ─────────────────────────────────────────────────────
    FIRMA_INICIADA   = "FIRMA_INICIADA"
    FIRMA_COMPLETADA = "FIRMA_COMPLETADA"
    FIRMA_CANCELADA  = "FIRMA_CANCELADA"

    # ── Documentos ────────────────────────────────────────────────────────────
    DOCUMENTO_CARGADO   = "DOCUMENTO_CARGADO"
    DOCUMENTO_ELIMINADO = "DOCUMENTO_ELIMINADO"

    # ── Integridad: detectado por trigger de BD ───────────────────────────────
    CAMBIO_DIRECTO_BD = "CAMBIO_DIRECTO_BD"


class ActorTipo:
    """Tipos de actor que puede originar un evento."""
    OPERADOR    = "OPERADOR"     # usuario del portal interno (Keycloak)
    CONTRAPARTE = "CONTRAPARTE"  # contraparte que llena el formulario
    SISTEMA     = "SISTEMA"      # webhook, proceso automatizado
    DB_DIRECTO  = "DB_DIRECTO"   # cambio directo en BD (bypass de aplicación)


@dataclass
class EventoAuditoria:
    """
    Registro inmutable de un evento del ciclo de vida de un formulario.

    Una vez persistido, nunca se modifica.
    """
    formulario_id: str
    tipo_evento: str
    estado_nuevo: str
    actor_tipo: str
    estado_anterior: Optional[str] = None
    actor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # Populado por la BD al persistir
    id: Optional[int] = None
    created_at: Optional[datetime] = None
