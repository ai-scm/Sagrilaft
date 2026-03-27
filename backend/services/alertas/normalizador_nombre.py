"""
Normalización de razones sociales para comparación tolerante.

Maneja variaciones comunes en datos colombianos extraídos por OCR o escritos
por usuarios:
  - Diacríticos:   Compañía → COMPANIA
  - Mayúsculas:    Empresa → EMPRESA
  - Abreviaciones: S.A.S. → SAS | LIMITADA → LTDA | Cía. → CIA
  - Espacios:      EMPRESA  X → EMPRESA X

SOLID:
- S (Responsabilidad Única): módulo dedicado exclusivamente a normalización.
- O (Abierto/Cerrado):      nuevas abreviaciones se agregan en _SIGLAS_SOCIETARIAS
                             sin tocar la lógica de normalización.

DRY: tabla de siglas centralizada; la misma lista se usa tanto en el backend
     como se refleja en el hook useAlertasRazonSocial del frontend.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple


# ── Siglas societarias colombianas más frecuentes ─────────────────────────────
# Orden: primero las más largas para evitar reemplazos parciales.
# Cada tupla: (patron_regex, forma_canónica)

_SIGLAS_SOCIETARIAS: List[Tuple[str, str]] = [
    # Formas largas → sigla canónica
    (r'SOCIEDAD POR ACCIONES SIMPLIFICADA', 'SAS'),
    (r'SOCIEDAD ANONIMA SIMPLIFICADA',      'SAS'),
    (r'SOCIEDAD DE RESPONSABILIDAD LIMITADA', 'LTDA'),
    (r'EMPRESA UNIPERSONAL',                'EU'),
    (r'SOCIEDAD ANONIMA',                   'SA'),
    (r'SOCIEDAD EN COMANDITA POR ACCIONES', 'SCA'),
    (r'SOCIEDAD EN COMANDITA SIMPLE',       'SCS'),
    (r'SOCIEDAD COLECTIVA',                 'SC'),
    # Formas abreviadas con puntos → sigla sin puntos
    (r'S\.A\.S\.?',   'SAS'),
    (r'S\.A\.?',      'SA'),
    (r'LTDA\.?',      'LTDA'),
    (r'LIMITADA\.?',  'LTDA'),
    (r'E\.U\.?',      'EU'),
    (r'S\.R\.L\.?',   'SRL'),
    (r'S\.C\.A\.?',   'SCA'),
    (r'S\.C\.S\.?',   'SCS'),
    (r'C\.I\.?',      'CI'),
    (r'E\.S\.P\.?',   'ESP'),
    (r'CÍA\.?',       'CIA'),
    (r'CIA\.?',       'CIA'),
    (r'CO\.?',        'CO'),
    (r'Y\s+CIA\.?',   'YCIA'),
]


def normalizar_razon_social(valor: str) -> str:
    """
    Normaliza una razón social para comparación tolerante.

    Aplica las transformaciones en este orden:
      1. Quitar diacríticos (tildes, ñ→n, ü→u).
      2. Convertir a mayúsculas.
      3. Sustituir siglas societarias por su forma canónica.
      4. Eliminar puntos residuales.
      5. Colapsar espacios múltiples.
      6. Strip.

    Args:
        valor: Razón social original (puede estar vacía o nula).

    Returns:
        Cadena normalizada en mayúsculas, sin diacríticos ni siglas con puntos.
        Retorna cadena vacía si valor es nulo o vacío.

    Examples:
        >>> normalizar_razon_social("Inversiones S.A.S.")
        'INVERSIONES SAS'
        >>> normalizar_razon_social("Compañía Ltda.")
        'COMPANIA LTDA'
        >>> normalizar_razon_social("EMPRESA X S.A.")
        'EMPRESA X SA'
    """
    if not valor:
        return ""

    # 1. Quitar diacríticos
    sin_tildes = unicodedata.normalize("NFD", str(valor))
    texto = sin_tildes.encode("ascii", "ignore").decode("ascii")

    # 2. Mayúsculas
    texto = texto.upper()

    # 3. Normalizar siglas societarias (primero las más largas)
    for patron, canonica in _SIGLAS_SOCIETARIAS:
        texto = re.sub(patron, canonica, texto)

    # 4. Eliminar puntos residuales
    texto = texto.replace(".", "")

    # 5. Colapsar espacios
    texto = re.sub(r"\s+", " ", texto)

    # 6. Strip
    return texto.strip()
