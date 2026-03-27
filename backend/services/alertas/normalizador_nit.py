"""
Normalización de NITs colombianos para comparación tolerante.

Maneja variaciones comunes en la representación del NIT:
  - Puntos de separación:  900.123.456   → 900123456
  - Guión de verificación: 900123456-7   → 900123456
  - Espacios:              900 123 456   → 900123456
  - Dígito de verificación incluido como 10.º dígito (sin guión)

SOLID:
- S (Responsabilidad Única): módulo dedicado exclusivamente a normalización de NIT.
- O (Abierto/Cerrado):      la lógica de normalización es extensible sin modificar
                             el comparador ni el detector.

DRY: función única de normalización; el comparador y el detector la reutilizan.
     El frontend espeja esta misma lógica en useAlertasNit.js.
"""

from __future__ import annotations

import re


# Longitud base del NIT colombiano sin dígito de verificación.
_LONGITUD_NIT_BASE = 9


def normalizar_nit(valor: str) -> str:
    """
    Normaliza un NIT colombiano para comparación tolerante.

    Aplica las transformaciones en este orden:
      1. Extraer solo dígitos (eliminar puntos, guiones, espacios, letras).
      2. Si el resultado tiene más de _LONGITUD_NIT_BASE dígitos, descartar
         los dígitos sobrantes desde el final (dígito de verificación).

    La truncatura al NIT base permite comparar valores extraídos de documentos
    distintos que difieren únicamente en la presencia del dígito de verificación:
    unos lo incluyen ("900123456-7" → "9001234567") y otros no ("900123456").

    Args:
        valor: NIT en cualquier formato (puede incluir puntos, guiones, etc.).

    Returns:
        Cadena de hasta _LONGITUD_NIT_BASE dígitos, o cadena vacía si la entrada
        es nula, vacía o no contiene dígitos.

    Examples:
        >>> normalizar_nit("900.123.456-7")
        '900123456'
        >>> normalizar_nit("900123456")
        '900123456'
        >>> normalizar_nit("9001234567")
        '900123456'
        >>> normalizar_nit("NIT 900.123.456")
        '900123456'
        >>> normalizar_nit("")
        ''
    """
    if not valor:
        return ""

    solo_digitos = re.sub(r"\D", "", str(valor))

    if len(solo_digitos) > _LONGITUD_NIT_BASE:
        return solo_digitos[:_LONGITUD_NIT_BASE]

    return solo_digitos
