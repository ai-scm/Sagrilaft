"""
Utilidades de cálculo de fechas para el dominio SAGRILAFT.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional


DIAS_HABILES_VIGENCIA_ACCESO = 5


def sumar_dias_habiles(desde: datetime, n_dias: int) -> datetime:
    """Suma n días hábiles (lunes–viernes) a partir de la fecha dada."""
    fecha = desde
    contados = 0
    while contados < n_dias:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5:  # 0=lunes … 4=viernes
            contados += 1
    return fecha


def ahora_utc() -> datetime:
    """Retorna el datetime actual en UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def normalizar_datetime_utc(valor: datetime) -> datetime:
    """Normaliza cualquier datetime a UTC aware (naive se asume UTC)."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def a_iso_utc_z(valor: Optional[datetime]) -> Optional[str]:
    """Serializa un datetime a ISO-8601 con zona UTC explícita ('Z')."""
    if valor is None:
        return None
    return normalizar_datetime_utc(valor).isoformat().replace("+00:00", "Z")


# Meses en español usados en cédulas colombianas (formato DD-MMM-AAAA)
_MESES_ES: dict[str, int] = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def parsear_fecha_colombia(valor: Any) -> Optional[date]:
    """Parsea fechas en formatos comunes del dominio colombiano.

    Formatos soportados:
      - YYYY-MM-DD   (formulario con <input type="date">)
      - DD-MMM-AAAA  (cédula colombiana; mes abreviado en español; ej: '01-SEP-1995')
    """
    if not valor:
        return None

    cadena = str(valor).strip()

    try:
        return datetime.strptime(cadena, "%Y-%m-%d").date()
    except ValueError:
        pass

    partes = cadena.split("-")
    if len(partes) == 3:
        dia_str, mes_str, anio_str = partes
        mes_num = _MESES_ES.get(mes_str.lower())
        if mes_num:
            try:
                return date(int(anio_str), mes_num, int(dia_str))
            except ValueError:
                return None

    return None

