"""
Utilidades compartidas entre validadores de documentos.

DRY: Centraliza lógica de normalización y validación de vigencia
     que antes se duplicaba en cada validador.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from services.contracts import ValidationFinding

DATE_FORMAT = "%Y-%m-%d"
VIGENCIA_MAX_DIAS = 30


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparación: minúsculas y sin espacios extremos."""
    return str(value).lower().strip() if value else ""


def normalize_id(value: Any) -> str:
    """Normaliza un número de identificación eliminando puntos, guiones y espacios."""
    if not value:
        return ""
    return str(value).replace(".", "").replace("-", "").replace(" ", "").strip()


def check_vigencia(
    fecha_str: Any,
    campo: str,
    max_dias: int = VIGENCIA_MAX_DIAS,
) -> Optional[ValidationFinding]:
    """
    Verifica que un documento no supere `max_dias` días de antigüedad.

    Returns:
        ValidationFinding ok/error, o None si la fecha no es parseable.
    """
    if not fecha_str:
        return None
    try:
        fecha = datetime.strptime(str(fecha_str), DATE_FORMAT)
        dias = (datetime.now() - fecha).days
        if dias > max_dias:
            return ValidationFinding.error(
                campo=campo,
                detalle=f"Documento tiene {dias} días. No debe superar {max_dias} días.",
                valor_documento=str(fecha_str),
            )
        return ValidationFinding.ok(
            campo=campo,
            detalle=f"Documento vigente ({dias} días).",
            valor_documento=str(fecha_str),
        )
    except ValueError:
        return None
