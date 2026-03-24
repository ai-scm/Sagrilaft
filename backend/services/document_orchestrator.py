"""
Orquestador de validación de documentos.

Coordina la extracción IA y la validación por tipo de documento.
Depende de abstracciones (IAIExtractor, IDocumentValidator), no de implementaciones.

Principio SOLID:
- O (Open/Closed): Agregar nuevos validadores sin modificar este orquestador.
- D (Dependency Inversion): Recibe dependencias via constructor.
"""

import logging
from typing import Any, Dict, List

from services.contracts import IAIExtractor, IDocumentValidator, ValidationFinding

logger = logging.getLogger(__name__)


class DocumentValidationOrchestrator:
    """
    Punto central de validación de documentos.
    
    Recibe un extractor IA y un conjunto de validadores registrados.
    Para cada documento: extrae datos con IA → selecciona validador → ejecuta.
    """

    def __init__(self, extractor: IAIExtractor):
        self._extractor = extractor
        self._validators: Dict[str, IDocumentValidator] = {}

    def register_validator(self, validator: IDocumentValidator) -> None:
        """Registra un validador para un tipo de documento."""
        self._validators[validator.document_type] = validator

    async def validate_document(
        self,
        file_path: str,
        document_type: str,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        """
        Valida un documento individual contra los datos del formulario.
        
        1. Extrae datos usando AWS Bedrock.
        2. Busca validador registrado para el tipo.
        3. Ejecuta validación y retorna hallazgos.
        """
        # Paso 1: Extracción IA
        extraction = await self._extractor.extract(file_path, document_type)

        logger.info(
            "Extracción %s: éxito=%s, confianza=%.2f",
            document_type, extraction.extraido, extraction.confianza
        )

        # Paso 2: Buscar validador
        validator = self._validators.get(document_type)
        if not validator:
            logger.warning("Sin validador registrado para: %s", document_type)
            return [ValidationFinding(
                resultado="advertencia",
                campo=document_type,
                detalle=f"No hay validador configurado para '{document_type}'. Requiere revisión manual.",
            )]

        # Paso 3: Validar
        return validator.validate(extraction, form_data)

    async def validate_all_documents(
        self,
        documents: List[Dict[str, str]],
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        """
        Valida una lista de documentos contra el formulario.
        
        Args:
            documents: Lista de dicts con 'file_path' y 'document_type'.
            form_data: Datos del formulario para contrastes.
        
        Returns:
            Lista consolidada de hallazgos.
        """
        all_findings: List[ValidationFinding] = []

        for doc in documents:
            findings = await self.validate_document(
                file_path=doc["file_path"],
                document_type=doc["document_type"],
                form_data=form_data,
            )
            all_findings.extend(findings)

        return all_findings

    @property
    def registered_types(self) -> List[str]:
        """Tipos de documento con validador registrado."""
        return list(self._validators.keys())
