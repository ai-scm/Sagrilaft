"""
Normalización de direcciones para comparación tolerante.

Maneja las variaciones más frecuentes en direcciones colombianas extraídas
por OCR o escritas por usuarios:
  - Diacríticos:    Módulo → MODULO
  - Mayúsculas:     calle → CALLE
  - Tipos viales:   Carrera → CR | CALLE → CL | AVENIDA → AV …
  - Separadores:    # | No. | Nro. → espacio
  - Puntuación:     puntos, comas → eliminados
  - Espacios:       colapso de múltiples espacios

SOLID:
- S (Responsabilidad Única): módulo dedicado exclusivamente a normalización de
                             direcciones; no contiene lógica de comparación.
- O (Abierto/Cerrado):       nuevos tipos viales se agregan en _TIPOS_VIALES
                             sin tocar la función normalizar_direccion.

DRY: tabla de abreviaciones centralizada; la misma lógica se refleja en el
     hook useAlertasDireccion del frontend.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from services.utils.texto import quitar_diacriticos


# ── Tipos viales colombianos más frecuentes ───────────────────────────────────
# Orden: primero las formas largas para evitar reemplazos parciales.
# Cada tupla: (patron_regex con \b, forma_canónica)

_TIPOS_VIALES: List[Tuple[str, str]] = [
    # Formas largas → sigla canónica
    (r'\bCALLE\b',       'CL'),
    (r'\bCARRERA\b',     'CR'),
    (r'\bAVENIDA\b',     'AV'),
    (r'\bDIAGONAL\b',   'DG'),
    (r'\bTRANSVERSAL\b', 'TV'),
    (r'\bCIRCULAR\b',   'CIC'),
    (r'\bAUTOPISTA\b',  'AU'),
    (r'\bVARIANTE\b',   'VT'),
    # Formas intermedias → sigla canónica
    (r'\bCLLE\b',  'CL'),
    (r'\bCLL\b',   'CL'),
    (r'\bCRRA\b',  'CR'),
    (r'\bCRA\b',   'CR'),
    (r'\bAVE\b',   'AV'),
    (r'\bDIAG\b',  'DG'),
    (r'\bTRANS\b', 'TV'),
    (r'\bCIRC\b',  'CIC'),
]

# ── Separadores de numeración ─────────────────────────────────────────────────
# Se reemplazan por espacio para unificar "# 19-40" ≈ "No 19-40" ≈ "Nro. 19-40"

_SEPARADORES_NUMERACION: List[Tuple[str, str]] = [
    (r'#',           ' '),
    (r'\bNUMERO\b',  ' '),
    (r'\bNRO\.?\b',  ' '),
    (r'\bNO\.?\b',   ' '),
]


def normalizar_direccion(valor: str) -> str:
    """
    Normaliza una dirección para comparación tolerante.

    Aplica las transformaciones en este orden:
      1. Quitar diacríticos (tildes, ñ→n, ü→u).
      2. Convertir a mayúsculas.
      3. Sustituir tipos viales por su forma canónica (Carrera → CR).
      4. Normalizar separadores de numeración (# | No. | Nro. → espacio).
      5. Eliminar puntuación residual (puntos, comas).
      6. Colapsar espacios múltiples y hacer strip.

    Args:
        valor: Dirección original (puede estar vacía o nula).

    Returns:
        Cadena normalizada en mayúsculas, sin diacríticos ni abreviaciones
        heterogéneas. Retorna cadena vacía si valor es nulo o vacío.

    Examples:
        >>> normalizar_direccion("Carrera 15 # 93-75")
        'CR 15 93-75'
        >>> normalizar_direccion("CALLE 100 No. 19-40")
        'CL 100 19-40'
        >>> normalizar_direccion("Cra. 7 Nro 72-64")
        'CR 7 72-64'
    """
    if not valor:
        return ""

    # 1. Quitar diacríticos
    texto = quitar_diacriticos(str(valor))

    # 2. Mayúsculas
    texto = texto.upper()

    # 3. Normalizar tipos viales (formas largas primero)
    for patron, canonica in _TIPOS_VIALES:
        texto = re.sub(patron, canonica, texto)

    # 4. Normalizar separadores de numeración
    for patron, reemplazo in _SEPARADORES_NUMERACION:
        texto = re.sub(patron, reemplazo, texto)

    # 5. Eliminar puntuación residual (puntos y comas que no forman parte de números)
    texto = re.sub(r'[.,]', '', texto)

    # 6. Colapsar espacios
    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip()
