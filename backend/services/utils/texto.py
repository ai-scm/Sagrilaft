"""
Utilidades de manipulación de texto compartidas entre subsistemas.

DRY: centraliza operaciones de texto que de otro modo se duplicarían en
     alertas/normalizadores, validators/_utils y listas/mock_providers.
SRP: cada función tiene una única transformación bien definida.
"""

import unicodedata


def quitar_diacriticos(valor: str) -> str:
    """
    Elimina diacríticos de una cadena: tildes, ñ→n, ü→u, etc.

    Usa descomposición Unicode NFD (separa base + modificador) y luego
    descarta todos los caracteres que no son ASCII puro.

    Args:
        valor: Cadena de texto original (se acepta cualquier tipo; se castea a str).

    Returns:
        La cadena sin diacríticos. Preserva mayúsculas/minúsculas y espacios.

    Examples:
        >>> quitar_diacriticos("Compañía")
        'Compania'
        >>> quitar_diacriticos("JOSÉ")
        'JOSE'
        >>> quitar_diacriticos("cédula")
        'cedula'
    """
    sin_tildes = unicodedata.normalize("NFD", str(valor))
    return sin_tildes.encode("ascii", "ignore").decode("ascii")
