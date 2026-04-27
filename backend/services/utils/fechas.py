"""
Utilidades de cálculo de fechas para el dominio SAGRILAFT.
"""

from datetime import datetime, timedelta


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
