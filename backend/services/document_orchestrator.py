"""
Orquestador de validación de documentos.

Coordina la extracción IA y la validación por tipo de documento.
Depende de abstracciones (IAIExtractor, IDocumentValidator), no de implementaciones.

Principio SOLID:
- O (Open/Closed): Agregar nuevos validadores sin modificar este orquestador.
- D (Dependency Inversion): Recibe dependencias via constructor.
"""

import logging
from typing import Any, Dict, List, Tuple

from services.contracts import ExtractionResult, IAIExtractor, IDocumentValidator, ValidationFinding
from services.validators._utils import normalize_id, normalize_text

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

    @property
    def extractor(self) -> IAIExtractor:
        """Expone el extractor IA para uso directo (ej. pre-llenado de formulario)."""
        return self._extractor

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
    ) -> Tuple[List[ValidationFinding], List[ValidationFinding]]:
        """
        Valida una lista de documentos contra el formulario y entre sí.

        Args:
            documents: Lista de dicts con 'file_path' y 'document_type'.
            form_data: Datos del formulario para contrastes.

        Returns:
            Tupla (hallazgos_individuales, hallazgos_cruzados).
            - hallazgos_individuales: cada documento vs formulario.
            - hallazgos_cruzados: consistencia entre documentos (cedula, RUT, Cámara).
        """
        individual_findings: List[ValidationFinding] = []
        extractions: Dict[str, Dict[str, Any]] = {}

        for doc in documents:
            doc_type = doc["document_type"]
            extraction = await self._extractor.extract(doc["file_path"], doc_type)

            logger.info(
                "Extracción %s: éxito=%s, confianza=%.2f",
                doc_type, extraction.extraido, extraction.confianza,
            )

            if extraction.extraido:
                extractions[doc_type] = extraction.datos

            validator = self._validators.get(doc_type)
            if not validator:
                logger.warning("Sin validador registrado para: %s", doc_type)
                individual_findings.append(ValidationFinding(
                    resultado="advertencia",
                    campo=doc_type,
                    detalle=f"No hay validador configurado para '{doc_type}'. Requiere revisión manual.",
                ))
            else:
                individual_findings.extend(validator.validate(extraction, form_data))

        cross_findings = self._cross_validate(extractions)
        return individual_findings, cross_findings

    def _cross_validate(
        self, extractions: Dict[str, Dict[str, Any]]
    ) -> List[ValidationFinding]:
        """
        Valida consistencia de datos entre los documentos adjuntos.

        Reglas:
        1. Cédula del representante (doc cédula) == cedula_representante (Cámara de Comercio)
        2. Cédula del representante (doc cédula) == cedula_representante (RUT, si está disponible)
        3. Razón social: RUT == Cámara de Comercio
        4. NIT: RUT == Cámara de Comercio
        5. Dirección: RUT == Cámara de Comercio
        """
        findings: List[ValidationFinding] = []
        rut = extractions.get("rut") or {}
        camara = extractions.get("certificado_existencia") or {}
        cedula = extractions.get("cedula_representante") or {}

        # ── 1. Cédula: doc cédula vs Cámara de Comercio ─────────────────
        ced_doc = normalize_id(cedula.get("numero_documento"))
        ced_camara = normalize_id(camara.get("cedula_representante"))
        if ced_doc and ced_camara:
            coincide = ced_doc == ced_camara
            findings.append(
                ValidationFinding.ok(
                    campo="cruce_cedula_vs_camara",
                    detalle="Cédula del representante coincide entre la cédula y el Certificado de Existencia.",
                    valor_formulario=camara.get("cedula_representante"),
                    valor_documento=cedula.get("numero_documento"),
                ) if coincide else ValidationFinding.error(
                    campo="cruce_cedula_vs_camara",
                    detalle="Cédula del representante NO coincide entre la cédula y el Certificado de Existencia.",
                    valor_formulario=camara.get("cedula_representante"),
                    valor_documento=cedula.get("numero_documento"),
                )
            )

        # ── 2. Cédula: doc cédula vs RUT ─────────────────────────────────
        ced_rut = normalize_id(rut.get("cedula_representante"))
        if ced_doc and ced_rut:
            coincide = ced_doc == ced_rut
            findings.append(
                ValidationFinding.ok(
                    campo="cruce_cedula_vs_rut",
                    detalle="Cédula del representante coincide entre la cédula y el RUT.",
                    valor_formulario=rut.get("cedula_representante"),
                    valor_documento=cedula.get("numero_documento"),
                ) if coincide else ValidationFinding.error(
                    campo="cruce_cedula_vs_rut",
                    detalle="Cédula del representante NO coincide entre la cédula y el RUT.",
                    valor_formulario=rut.get("cedula_representante"),
                    valor_documento=cedula.get("numero_documento"),
                )
            )

        # ── 3. Razón social: RUT vs Cámara de Comercio ───────────────────
        rs_rut = normalize_text(rut.get("razon_social"))
        rs_camara = normalize_text(camara.get("razon_social"))
        if rs_rut and rs_camara:
            coincide = rs_rut == rs_camara
            findings.append(
                ValidationFinding.ok(
                    campo="cruce_razon_social",
                    detalle="Razón social coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("razon_social"),
                    valor_documento=rut.get("razon_social"),
                ) if coincide else ValidationFinding.error(
                    campo="cruce_razon_social",
                    detalle="Razón social NO coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("razon_social"),
                    valor_documento=rut.get("razon_social"),
                )
            )

        # ── 4. NIT: RUT vs Cámara de Comercio ────────────────────────────
        nit_rut = normalize_id(rut.get("nit"))
        nit_camara = normalize_id(camara.get("nit"))
        if nit_rut and nit_camara:
            coincide = nit_rut == nit_camara
            findings.append(
                ValidationFinding.ok(
                    campo="cruce_nit",
                    detalle="NIT coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("nit"),
                    valor_documento=rut.get("nit"),
                ) if coincide else ValidationFinding.error(
                    campo="cruce_nit",
                    detalle="NIT NO coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("nit"),
                    valor_documento=rut.get("nit"),
                )
            )

        # ── 5. Dirección: RUT vs Cámara de Comercio ──────────────────────
        dir_rut = normalize_text(rut.get("direccion"))
        dir_camara = normalize_text(camara.get("direccion"))
        if dir_rut and dir_camara:
            coincide = dir_rut == dir_camara
            findings.append(
                ValidationFinding.ok(
                    campo="cruce_direccion",
                    detalle="Dirección coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("direccion"),
                    valor_documento=rut.get("direccion"),
                ) if coincide else ValidationFinding.error(
                    campo="cruce_direccion",
                    detalle="Dirección NO coincide entre RUT y Certificado de Existencia.",
                    valor_formulario=camara.get("direccion"),
                    valor_documento=rut.get("direccion"),
                )
            )

        return findings

    @property
    def registered_types(self) -> List[str]:
        """Tipos de documento con validador registrado."""
        return list(self._validators.keys())
