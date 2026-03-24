"""
Validador: Certificado de Existencia y Representación Legal (Cámara de Comercio).

Alarmas que implementa:
- Razón social no coincide
- NIT no coincide
- Representante legal no coincide
- Cédula del representante no coincide
- Certificado con más de 30 días
"""

from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding
from services.validators._utils import check_vigencia, normalize_id, normalize_text


class CamaraComercioValidator:
    """Valida Certificado de Cámara de Comercio contra datos del formulario."""

    @property
    def document_type(self) -> str:
        return "certificado_existencia"

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        if not extracted_data.extraido:
            return [ValidationFinding.advertencia(
                campo="certificado_existencia",
                detalle=f"No se pudieron extraer datos. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos
        source = "certificado de Cámara de Comercio"

        # --- Razón social ---
        findings.append(self._compare_text(
            datos.get("razon_social"), form_data.get("razon_social"),
            campo="razon_social", nombre="Razón social", source=source,
        ))

        # --- NIT ---
        findings.append(self._compare_nit(
            datos.get("nit"), form_data.get("numero_identificacion"),
        ))

        # --- Representante legal ---
        findings.append(self._compare_text(
            datos.get("representante_legal"), form_data.get("nombre_representante"),
            campo="nombre_representante", nombre="Representante legal", source=source,
        ))

        # --- Cédula del representante ---
        findings.append(self._compare_nit(
            datos.get("cedula_representante"), form_data.get("numero_doc_representante"),
            campo="numero_doc_representante", nombre="Cédula del representante",
        ))

        # --- Vigencia del certificado (≤ 30 días) ---
        finding_fecha = check_vigencia(datos.get("fecha_documento"), campo="fecha_certificado_camara")
        if finding_fecha:
            findings.append(finding_fecha)

        return [f for f in findings if f is not None]

    # ── Helpers privados ──────────────────────────────────

    @staticmethod
    def _compare_text(
        doc_value: Any, form_value: Any,
        campo: str, nombre: str, source: str,
    ) -> ValidationFinding | None:
        if not doc_value or not form_value:
            return None
        coincide = normalize_text(doc_value) == normalize_text(form_value)
        return (
            ValidationFinding.ok(
                campo=campo,
                detalle=f"{nombre} coincide con {source}.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            ) if coincide else ValidationFinding.error(
                campo=campo,
                detalle=f"{nombre} NO coincide entre {source} y el formulario.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            )
        )

    @staticmethod
    def _compare_nit(
        doc_value: Any, form_value: Any,
        campo: str = "numero_identificacion",
        nombre: str = "NIT",
    ) -> ValidationFinding | None:
        if not doc_value or not form_value:
            return None
        coincide = normalize_id(doc_value) == normalize_id(form_value)
        return (
            ValidationFinding.ok(
                campo=campo, detalle=f"{nombre} coincide.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            ) if coincide else ValidationFinding.error(
                campo=campo,
                detalle=f"{nombre} NO coincide entre el certificado y el formulario.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            )
        )
