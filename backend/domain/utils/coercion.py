from typing import Any

from domain.constantes import PORCENTAJE_MAXIMO_PERMITIDO


def limpiar_numero_id_si_tipo_ausente(data: Any) -> Any:
    """Garantiza que numero_id sea nulo cuando tipo_id no está definido."""
    if isinstance(data, dict) and not data.get('tipo_id'):
        data = {**data, 'numero_id': None}
    return data


def limpiar_vinculos_pep_si_no_es_pep(data: Any) -> Any:
    """Garantiza que vinculos_pep sea 'NA' cuando es_pep es 'no'."""
    if isinstance(data, dict) and data.get('es_pep') == 'no':
        data = {**data, 'vinculos_pep': 'NA'}
    return data


def vacio_a_nulo(v: object) -> object:
    """Coerciona strings vacíos a None pre-validación. Imprescindible para borradores."""
    return None if v == "" else v


def coercionar_monto(v: object) -> float | None:
    """
    Coerciona un valor de entrada (str o float) a float no negativo.
    Cadenas vacías y None se interpretan como ausencia de valor (None).
    Rechaza valores negativos ya que los montos financieros no pueden serlo.
    """
    if v is None or v == '':
        return None
    try:
        valor = float(v)
    except (TypeError, ValueError):
        raise ValueError('Debe ser un número válido')
    if valor < 0:
        raise ValueError('El monto no puede ser negativo')
    return valor


def coercionar_porcentaje(v: object) -> float | None:
    """
    Coerciona un valor de entrada (str o float) a float en rango [0, PORCENTAJE_MAXIMO_PERMITIDO].
    Cadenas vacías y None se interpretan como ausencia de valor (None).
    """
    if v is None or v == '':
        return None
    try:
        valor = float(v)
    except (TypeError, ValueError):
        raise ValueError(f'Debe ser un número válido entre 0 y {PORCENTAJE_MAXIMO_PERMITIDO}')
    if valor < 0:
        raise ValueError('El porcentaje no puede ser negativo')
    if valor > PORCENTAJE_MAXIMO_PERMITIDO:
        raise ValueError(f'El porcentaje no puede superar {PORCENTAJE_MAXIMO_PERMITIDO}')
    return valor


def coercionar_porcentaje_participacion(v: object) -> float | None:
    """
    Coerciona porcentaje de participación accionaria o control efectivo.
    Rango permitido: [0, PORCENTAJE_MAXIMO_PERMITIDO].
    El 100% es válido cuando la tabla solo tiene un registro.
    """
    valor = coercionar_porcentaje(v)
    if valor is not None and valor > PORCENTAJE_MAXIMO_PERMITIDO:
        raise ValueError(f'El porcentaje de participación no puede superar el {PORCENTAJE_MAXIMO_PERMITIDO}%')
    return valor
