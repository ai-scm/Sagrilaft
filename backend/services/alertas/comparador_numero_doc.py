"""
Comparador de números de documento de identidad entre formulario y documento.

Produce un ResultadoComparacionNumeroDoc inmutable con los valores originales,
los normalizados y el veredicto de coincidencia.

A diferencia de ComparadorNit, no trunca la longitud; los números de documento
(CC, CE, PAS) no tienen dígito de verificación a descartar.

SOLID:
- S (Responsabilidad Única): única responsabilidad — decidir si dos números de
                             documento son equivalentes después de normalización.
- D (Inversión de Dependencias): depende de normalizar_numero_doc (módulo neutral),
                                 no de lógica de comparación en línea.

DRY: la normalización vive en normalizador_numero_doc.py; ComparadorNumeroDoc
     no repite esa lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.alertas.normalizador_numero_doc import normalizar_numero_doc


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoComparacionNumeroDoc:
    """
    Resultado de comparar el número de documento del formulario contra el del
    documento adjunto.

    Attributes:
        coincide:                   True si los números normalizados son iguales.
        valor_formulario_original:  Número tal como aparece en el formulario.
        valor_documento_original:   Número tal como fue extraído del documento.
        valor_formulario_normalizado: Forma canónica del número del formulario.
        valor_documento_normalizado:  Forma canónica del número del documento.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


# ── Comparador ────────────────────────────────────────────────────────────────

class ComparadorNumeroDoc:
    """
    Determina si dos números de documento son equivalentes aplicando normalización.

    Tolera diferencias de:
      - Puntos separadores:   1.234.567 ≈ 1234567
      - Guiones:              AB-123456 ≈ AB123456
      - Espacios adicionales
      - Mayúsculas/minúsculas: ab123   ≈ AB123

    Aplica a CC (dígitos), CE (dígitos) y PAS (alfanumérico).

    SRP: única responsabilidad — evaluar equivalencia de números de documento.
    """

    def comparar(
        self,
        valor_formulario: Optional[str],
        valor_documento: Optional[str],
    ) -> Optional[ResultadoComparacionNumeroDoc]:
        """
        Compara dos números de documento normalizados.

        Args:
            valor_formulario: Número ingresado por el usuario en el formulario.
            valor_documento:  Número extraído del documento por IA.

        Returns:
            ResultadoComparacionNumeroDoc con el veredicto, o None si algún valor
            está ausente o vacío (sin datos suficientes para comparar).
        """
        norm_form = normalizar_numero_doc(valor_formulario or "")
        norm_doc  = normalizar_numero_doc(valor_documento  or "")

        if not norm_form or not norm_doc:
            return None

        return ResultadoComparacionNumeroDoc(
            coincide=norm_form == norm_doc,
            valor_formulario_original=str(valor_formulario),
            valor_documento_original=str(valor_documento),
            valor_formulario_normalizado=norm_form,
            valor_documento_normalizado=norm_doc,
        )
