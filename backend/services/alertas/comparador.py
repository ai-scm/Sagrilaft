"""
Comparador genérico de campos entre formulario y documentos.

Reemplaza las cuatro clases específicas anteriores que comparaban
razón social, NIT, número de documento y dirección respectivamente.
El comportamiento de cada una se obtiene inyectando el normalizador
correspondiente en el constructor.

El comportamiento de cada comparador se obtiene inyectando el normalizador
correspondiente en el constructor.

SOLID:
- S (Responsabilidad Única): única responsabilidad — decidir si dos valores son
                             equivalentes después de normalización.
- O (Abierto/Cerrado):       soportar un nuevo tipo de campo = instanciar Comparador
                             con su normalizador. No modificar esta clase.
- D (Inversión de Dependencias): recibe el normalizador como dependencia;
                                 no importa implementaciones concretas.

DRY: la lógica de comparación (normalizar → verificar vacío → comparar → construir
     resultado) vive en un único lugar en lugar de repetirse en cuatro archivos.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from core.contratos import ResultadoComparacion


class Comparador:
    """
    Compara dos valores de texto aplicando una función de normalización inyectada.

    Uso:
        comparador = Comparador(normalizar_razon_social)
        resultado  = comparador.comparar(valor_formulario, valor_documento)

    El resultado es un ResultadoComparacion inmutable con el veredicto y los
    valores originales y normalizados para trazabilidad.
    """

    def __init__(self, normalizador: Callable[[Any], str]) -> None:
        """
        Args:
            normalizador: Función que convierte un valor crudo a su forma canónica
                          para comparación (ej. normalizar_razon_social, normalizar_nit).
        """
        self._normalizador = normalizador

    def comparar(
        self,
        valor_formulario: Optional[str],
        valor_documento: Optional[str],
    ) -> Optional[ResultadoComparacion]:
        """
        Compara dos valores normalizados.

        Args:
            valor_formulario: Valor ingresado por el usuario en el formulario.
            valor_documento:  Valor extraído del documento por IA.

        Returns:
            ResultadoComparacion con el veredicto y los valores para trazabilidad,
            o None si alguno de los valores está ausente o vacío tras normalización.
        """
        norm_form = self._normalizador(valor_formulario or "")
        norm_doc  = self._normalizador(valor_documento  or "")

        if not norm_form or not norm_doc:
            return None

        return ResultadoComparacion(
            coincide=norm_form == norm_doc,
            valor_formulario_original=str(valor_formulario),
            valor_documento_original=str(valor_documento),
            valor_formulario_normalizado=norm_form,
            valor_documento_normalizado=norm_doc,
        )
