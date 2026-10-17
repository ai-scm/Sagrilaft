"""
Puertos para la validación de documentos individuales y su consistencia cruzada.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable

from domain.contratos.documentos import ResultadoExtraccion
from domain.contratos.validacion import HallazgoValidacion


@runtime_checkable
class ValidadorDocumentoImp(Protocol):
    """
    Interfaz para validadores de documentos específicos.

    Cada tipo de documento (Cámara de Comercio, RUT, etc.) tiene
    su propio validador que implementa este Protocolo.

    SOLID - S: Cada validador tiene una única responsabilidad.
    SOLID - L: Los subtipos son intercambiables sin romper el orquestador.
    """

    @property
    def tipo_documento(self) -> str:
        """Tipo de documento que valida (ej: 'certificado_existencia')."""
        ...

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """Compara datos extraídos del documento contra datos del formulario."""
        ...


@runtime_checkable
class ValidadorCruzadoImp(Protocol):
    """
    Interfaz para la validación de consistencia entre documentos.

    SOLID - S: Responsabilidad única: verificar coherencia entre documentos.
    SOLID - I: Interfaz mínima y enfocada, separada de ValidadorDocumentoImp.
    SOLID - D: El orquestador depende de esta abstracción, no de implementaciones.
    """

    def validar_cruzado(
        self,
        extracciones: Dict[str, Dict[str, Any]],
    ) -> List[HallazgoValidacion]:
        """Verifica la consistencia de datos entre los documentos adjuntos."""
        ...
