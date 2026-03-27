"""
Comparador de razón social entre formulario y documento.

Produce un ResultadoComparacion inmutable con los valores originales,
los normalizados y el veredicto de coincidencia.

SOLID:
- S (Responsabilidad Única): única responsabilidad — decidir si dos nombres son
                             equivalentes después de normalización.
- D (Inversión de Dependencias): depende de normalizar_razon_social (módulo
                                 neutral), no de lógica de comparación en línea.

DRY: la normalización vive en normalizador_nombre.py; ComparadorRazonSocial
     no repite esa lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.alertas.normalizador_nombre import normalizar_razon_social


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoComparacion:
    """
    Resultado de comparar la razón social del formulario contra la del documento.

    Attributes:
        coincide:                   True si los nombres normalizados son iguales.
        valor_formulario_original:  Texto tal como aparece en el formulario.
        valor_documento_original:   Texto tal como fue extraído del documento.
        valor_formulario_normalizado: Forma canónica del nombre del formulario.
        valor_documento_normalizado:  Forma canónica del nombre del documento.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


# ── Comparador ────────────────────────────────────────────────────────────────

class ComparadorRazonSocial:
    """
    Determina si dos razones sociales son equivalentes aplicando normalización.

    Tolera diferencias de:
      - Mayúsculas / minúsculas
      - Tildes y diacríticos (Compañía ≈ Compania)
      - Abreviaciones societarias (S.A.S. ≈ SAS, LTDA. ≈ LIMITADA)
      - Espacios adicionales

    SRP: única responsabilidad — evaluar equivalencia de nombres.
    """

    def comparar(
        self,
        valor_formulario: Optional[str],
        valor_documento: Optional[str],
    ) -> Optional[ResultadoComparacion]:
        """
        Compara dos razones sociales normalizadas.

        Args:
            valor_formulario: Razón social ingresada por el usuario.
            valor_documento:  Razón social extraída del documento por IA.

        Returns:
            ResultadoComparacion con el veredicto, o None si algún valor está
            ausente o vacío (sin datos suficientes para comparar).
        """
        norm_form = normalizar_razon_social(valor_formulario or "")
        norm_doc  = normalizar_razon_social(valor_documento  or "")

        if not norm_form or not norm_doc:
            return None

        return ResultadoComparacion(
            coincide=norm_form == norm_doc,
            valor_formulario_original=str(valor_formulario),
            valor_documento_original=str(valor_documento),
            valor_formulario_normalizado=norm_form,
            valor_documento_normalizado=norm_doc,
        )
