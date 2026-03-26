"""
Orquestador de validación de documentos.

Coordina la extracción IA y la validación por tipo de documento.
Depende exclusivamente de abstracciones (IExtractorIA, IValidadorDocumento,
IValidadorCruzado), nunca de implementaciones concretas.

SOLID:
- S (Responsabilidad Única): Solo coordina el flujo; la lógica de cruce
  vive en IValidadorCruzado; cada validador individual en IValidadorDocumento.
- O (Abierto/Cerrado): Agregar nuevos validadores o reglas de cruce no
  requiere modificar este orquestador.
- D (Inversión de Dependencias): Recibe todas las dependencias vía constructor.

DRY: La extracción con log y la ejecución del validador están centralizadas
     en métodos privados reutilizados por ambos métodos públicos de validación.
"""

import logging
from typing import Any, Dict, List, Tuple

from services.contracts import (
    HallazgoValidacion,
    IExtractorIA,
    IValidadorCruzado,
    IValidadorDocumento,
    ResultadoExtraccion,
)

logger = logging.getLogger(__name__)


class OrquestadorValidacionDocumentos:
    """
    Punto central de validación de documentos.

    Para cada documento: extrae datos con IA → selecciona validador → ejecuta.
    Al final, delega la validación cruzada al IValidadorCruzado inyectado.
    """

    def __init__(
        self,
        extractor: IExtractorIA,
        validador_cruzado: IValidadorCruzado,
    ) -> None:
        """
        Args:
            extractor:        Implementación de extracción IA (ej. ExtractorBedrock).
            validador_cruzado: Implementación de validación cruzada entre documentos.
        """
        self._extractor = extractor
        self._validador_cruzado = validador_cruzado
        self._validadores: Dict[str, IValidadorDocumento] = {}

    @property
    def extractor(self) -> IExtractorIA:
        """Expone el extractor IA para uso directo (ej. pre-llenado de formulario)."""
        return self._extractor

    def registrar_validador(self, validador: IValidadorDocumento) -> None:
        """Registra un validador para un tipo de documento."""
        self._validadores[validador.tipo_documento] = validador

    @property
    def tipos_registrados(self) -> List[str]:
        """Tipos de documento con validador registrado."""
        return list(self._validadores.keys())

    # ─── Métodos públicos de validación ──────────────────────────────────────

    async def validar_documento(
        self,
        ruta_archivo: str,
        tipo_documento: str,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Valida un documento individual contra los datos del formulario.

        Flujo: extrae con IA → busca validador → ejecuta validación.

        Args:
            ruta_archivo:     Ruta local al archivo del documento.
            tipo_documento:   Clave del tipo de documento a procesar.
            datos_formulario: Datos del formulario para la validación.
        """
        extraccion = await self._extraer_con_log(ruta_archivo, tipo_documento)
        return self._ejecutar_validador(extraccion, tipo_documento, datos_formulario)

    async def validar_todos_documentos(
        self,
        documentos: List[Dict[str, str]],
        datos_formulario: Dict[str, Any],
    ) -> Tuple[List[HallazgoValidacion], List[HallazgoValidacion]]:
        """
        Valida una lista de documentos contra el formulario y entre sí.

        Args:
            documentos:       Lista de dicts con 'ruta_archivo' y 'tipo_documento'.
            datos_formulario: Datos del formulario para contrastes.

        Returns:
            Tupla (hallazgos_individuales, hallazgos_cruzados).
            - hallazgos_individuales: cada documento vs formulario.
            - hallazgos_cruzados: consistencia entre documentos.
        """
        hallazgos_individuales: List[HallazgoValidacion] = []
        extracciones: Dict[str, Dict[str, Any]] = {}

        for doc in documentos:
            tipo = doc["tipo_documento"]
            extraccion = await self._extraer_con_log(doc["ruta_archivo"], tipo)

            if extraccion.extraido:
                extracciones[tipo] = extraccion.datos

            hallazgos_individuales.extend(
                self._ejecutar_validador(extraccion, tipo, datos_formulario)
            )

        hallazgos_cruzados = self._validador_cruzado.validar_cruzado(extracciones)
        return hallazgos_individuales, hallazgos_cruzados

    # ─── Helpers privados ────────────────────────────────────────────────────

    async def _extraer_con_log(
        self,
        ruta_archivo: str,
        tipo_documento: str,
    ) -> ResultadoExtraccion:
        """Extrae datos de un documento y registra el resultado en el log."""
        extraccion = await self._extractor.extraer(ruta_archivo, tipo_documento)
        logger.info(
            "Extracción %s: éxito=%s, confianza=%.2f",
            tipo_documento, extraccion.extraido, extraccion.confianza,
        )
        return extraccion

    def _ejecutar_validador(
        self,
        extraccion: ResultadoExtraccion,
        tipo_documento: str,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """Busca el validador registrado para el tipo y ejecuta la validación."""
        validador = self._validadores.get(tipo_documento)
        if not validador:
            logger.warning("Sin validador registrado para: %s", tipo_documento)
            return [HallazgoValidacion.advertencia(
                campo=tipo_documento,
                detalle=f"No hay validador configurado para '{tipo_documento}'. Requiere revisión manual.",
            )]
        return validador.validar(extraccion, datos_formulario)
