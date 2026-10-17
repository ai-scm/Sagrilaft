"""
Entidades y Value Objects de documentos adjuntos y extracción IA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class DocumentoDatos:
    """
    Snapshot de un documento adjunto al formulario.

    Entidad de dominio libre de SQLAlchemy — reemplaza DocumentoAdjunto ORM
    en la capa de aplicación. Los repositorios realizan el mapping internamente.
    """
    id: str
    formulario_id: str
    tipo_documento: str
    nombre_archivo: str
    ruta_archivo: str
    content_type: Optional[str] = None
    tamano: Optional[int] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # ── Trazabilidad de versiones ──────────────────────────────────────────────
    version_numero: int = 1
    version_anterior_id: Optional[str] = None
    hash_sha256: Optional[str] = None
    subido_por: Optional[str] = None
    snapshot_datos: Optional[Dict[str, Any]] = None


@dataclass
class ResultadoExtraccion:
    """
    Resultado de la extracción IA de un documento.

    Attributes:
        extraido:   True si la extracción fue exitosa.
        datos:      Campos estructurados extraídos del documento.
        mensaje:    Descripción del resultado o del error ocurrido.
        confianza:  Nivel de confianza de la extracción (0.0 a 1.0).
    """
    extraido: bool
    datos: Dict[str, Any] = field(default_factory=dict)
    mensaje: str = ""
    confianza: float = 0.0
