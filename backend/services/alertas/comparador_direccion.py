"""
Comparador de direcciones entre formulario y documento.

Produce un ResultadoComparacionDireccion inmutable con los valores originales,
los normalizados y el veredicto de coincidencia.

SOLID:
- S (Responsabilidad Única): única responsabilidad — decidir si dos direcciones
                             son equivalentes después de normalización.
- D (Inversión de Dependencias): depende de normalizar_direccion (módulo neutral),
                                 no de lógica de normalización en línea.

DRY: la normalización vive en normalizador_direccion.py; ComparadorDireccion
     no repite esa lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.alertas.normalizador_direccion import normalizar_direccion


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoComparacionDireccion:
    """
    Resultado de comparar la dirección del formulario contra la del documento.

    Attributes:
        coincide:                     True si las direcciones normalizadas son iguales.
        valor_formulario_original:    Dirección tal como aparece en el formulario.
        valor_documento_original:     Dirección tal como fue extraída del documento.
        valor_formulario_normalizado: Forma canónica de la dirección del formulario.
        valor_documento_normalizado:  Forma canónica de la dirección del documento.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


# ── Comparador ────────────────────────────────────────────────────────────────

class ComparadorDireccion:
    """
    Determina si dos direcciones son equivalentes aplicando normalización.

    Tolera diferencias de:
      - Mayúsculas / minúsculas
      - Tildes y diacríticos       (Módulo ≈ Modulo)
      - Tipos viales abreviados    (Carrera 15 ≈ CR 15 ≈ Cra 15)
      - Separadores de numeración  (# 19-40 ≈ No. 19-40 ≈ Nro 19-40)
      - Puntuación residual        (Cl. 100 ≈ Cl 100)
      - Espacios adicionales

    SRP: única responsabilidad — evaluar equivalencia de direcciones.
    """

    def comparar(
        self,
        valor_formulario: Optional[str],
        valor_documento: Optional[str],
    ) -> Optional[ResultadoComparacionDireccion]:
        """
        Compara dos direcciones normalizadas.

        Args:
            valor_formulario: Dirección ingresada por el usuario en el formulario.
            valor_documento:  Dirección extraída del documento por IA.

        Returns:
            ResultadoComparacionDireccion con el veredicto, o None si algún valor
            está ausente o vacío (sin datos suficientes para comparar).
        """
        norm_form = normalizar_direccion(valor_formulario or "")
        norm_doc  = normalizar_direccion(valor_documento  or "")

        if not norm_form or not norm_doc:
            return None

        return ResultadoComparacionDireccion(
            coincide=norm_form == norm_doc,
            valor_formulario_original=str(valor_formulario),
            valor_documento_original=str(valor_documento),
            valor_formulario_normalizado=norm_form,
            valor_documento_normalizado=norm_doc,
        )
