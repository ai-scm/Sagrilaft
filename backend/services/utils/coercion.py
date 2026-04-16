
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
    Coerciona un valor de entrada (str o float) a float en rango [0, 100].
    Cadenas vacías y None se interpretan como ausencia de valor (None).
    """
    if v is None or v == '':
        return None
    try:
        valor = float(v)
    except (TypeError, ValueError):
        raise ValueError('Debe ser un número válido entre 0 y 100')
    if valor < 0:
        raise ValueError('El porcentaje no puede ser negativo')
    if valor > 100:
        raise ValueError('El porcentaje no puede superar 100')
    return valor


def coercionar_porcentaje_participacion(v: object) -> float | None:
    """
    Coerciona porcentaje de participación accionaria o control efectivo.
    Rango permitido: (0, 100) exclusivo — ningún titular puede ostentar el 100%,
    pues la figura aplica solo cuando existen múltiples partes.
    """
    valor = coercionar_porcentaje(v)
    if valor is not None and valor >= 100:
        raise ValueError('El porcentaje de participación no puede ser igual o superior al 100%')
    return valor
