"""
Comparador de NITs entre formulario y documento.

Produce un ResultadoComparacionNit inmutable con los valores originales,
los normalizados y el veredicto de coincidencia.

SOLID:
- S (Responsabilidad Única): única responsabilidad — decidir si dos NITs son
                             equivalentes después de normalización.
- D (Inversión de Dependencias): depende de normalizar_nit (módulo neutral),
                                 no de lógica de comparación en línea.

DRY: la normalización vive en normalizador_nit.py; ComparadorNit no repite
     esa lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.alertas.normalizador_nit import normalizar_nit


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoComparacionNit:
    """
    Resultado de comparar el NIT del formulario contra el del documento.

    Attributes:
        coincide:                   True si los NITs normalizados son iguales.
        valor_formulario_original:  NIT tal como aparece en el formulario.
        valor_documento_original:   NIT tal como fue extraído del documento.
        valor_formulario_normalizado: Forma canónica del NIT del formulario.
        valor_documento_normalizado:  Forma canónica del NIT del documento.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


# ── Comparador ────────────────────────────────────────────────────────────────

class ComparadorNit:
    """
    Determina si dos NITs son equivalentes aplicando normalización.

    Tolera diferencias de:
      - Puntos separadores:   900.123.456 ≈ 900123456
      - Dígito de verificación: 900123456-7 ≈ 900123456
      - Espacios adicionales
      - Prefijos textuales: "NIT 900123456" ≈ "900123456"

    SRP: única responsabilidad — evaluar equivalencia de NITs.
    """

    def comparar(
        self,
        valor_formulario: Optional[str],
        valor_documento: Optional[str],
    ) -> Optional[ResultadoComparacionNit]:
        """
        Compara dos NITs normalizados.

        Args:
            valor_formulario: NIT ingresado por el usuario en el formulario.
            valor_documento:  NIT extraído del documento por IA.

        Returns:
            ResultadoComparacionNit con el veredicto, o None si algún valor está
            ausente o vacío (sin datos suficientes para comparar).
        """
        norm_form = normalizar_nit(valor_formulario or "")
        norm_doc  = normalizar_nit(valor_documento  or "")

        if not norm_form or not norm_doc:
            return None

        return ResultadoComparacionNit(
            coincide=norm_form == norm_doc,
            valor_formulario_original=str(valor_formulario),
            valor_documento_original=str(valor_documento),
            valor_formulario_normalizado=norm_form,
            valor_documento_normalizado=norm_doc,
        )
