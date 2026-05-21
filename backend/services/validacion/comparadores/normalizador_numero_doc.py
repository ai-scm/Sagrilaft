"""
Normalizador del número de documento de identidad para comparación tolerante.

Elimina caracteres no alfanuméricos y convierte a mayúsculas para unificar
variantes de formato (puntos, guiones, espacios) presentes tanto en el formulario
como en los documentos extraídos por IA.

Aplica a cédulas de ciudadanía (CC), cédulas de extranjería (CE) y pasaportes (PAS).
No trunca la longitud (a diferencia de normalizador_nit.py), porque los números de
documento no tienen dígito de verificación que descartar.

SRP: única responsabilidad — producir una forma canónica de un número de documento.
DRY: función única invocada desde Comparador; no se repite la lógica.
"""

import re


def normalizar_numero_doc(valor: str) -> str:
    """
    Normaliza un número de documento eliminando caracteres no alfanuméricos
    y convirtiendo a mayúsculas.

    Tolerancias aplicadas:
      - Puntos separadores:   1.234.567 → 1234567
      - Guiones:              AB-123456 → AB123456
      - Espacios:             12 345    → 12345
      - Mayúsculas/minúsculas: ab123   → AB123

    Args:
        valor: Número de documento tal como aparece en el formulario o documento.

    Returns:
        Cadena normalizada (solo letras mayúsculas y dígitos), o "" si el
        valor es vacío o None.

    Examples:
        >>> normalizar_numero_doc("1.234.567")
        '1234567'
        >>> normalizar_numero_doc("AB-123456")
        'AB123456'
        >>> normalizar_numero_doc("  98765432  ")
        '98765432'
    """
    if not valor:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())
