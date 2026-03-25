"""
Validador: Cédula del Representante Legal.

Alarmas:
- Nombre no coincide con el formulario
- Número de documento no coincide
"""

from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding
from services.validators._utils import normalize_id, normalize_text, parse_fecha


class CedulaValidator:
    """Valida cédula del representante contra datos del formulario."""

    @property
    def document_type(self) -> str:
        return "cedula_representante"

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        if not extracted_data.extraido:
            return [ValidationFinding.advertencia(
                campo="cedula_representante",
                detalle=f"No se pudieron extraer datos de la cédula. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Nombre del representante ---
        doc_nombre = datos.get("nombre")
        form_nombre = form_data.get("nombre_representante")
        if doc_nombre and form_nombre:
            coincide = normalize_text(doc_nombre) == normalize_text(form_nombre)
            findings.append(
                ValidationFinding.ok(
                    campo="nombre_representante_cedula",
                    detalle="Nombre del representante coincide con la cédula.",
                    valor_formulario=str(form_nombre),
                    valor_documento=str(doc_nombre),
                ) if coincide else ValidationFinding.error(
                    campo="nombre_representante_cedula",
                    detalle="Nombre del representante NO coincide con la cédula.",
                    valor_formulario=str(form_nombre),
                    valor_documento=str(doc_nombre),
                )
            )

        # --- Número de documento ---
        doc_num = datos.get("numero_documento")
        form_num = form_data.get("numero_doc_representante")
        if doc_num and form_num:
            coincide = normalize_id(doc_num) == normalize_id(form_num)
            findings.append(
                ValidationFinding.ok(
                    campo="numero_doc_representante_cedula",
                    detalle="Número de cédula coincide.",
                    valor_formulario=str(form_num),
                    valor_documento=str(doc_num),
                ) if coincide else ValidationFinding.error(
                    campo="numero_doc_representante_cedula",
                    detalle="Número de cédula NO coincide entre el documento y el formulario.",
                    valor_formulario=str(form_num),
                    valor_documento=str(doc_num),
                )
            )

        # --- Tipo de documento ---
        doc_tipo = datos.get("tipo_documento")
        form_tipo = form_data.get("tipo_doc_representante")
        if doc_tipo and form_tipo:
            if normalize_text(doc_tipo) != normalize_text(form_tipo):
                findings.append(ValidationFinding.error(
                    campo="tipo_doc_representante_cedula",
                    detalle="Tipo de documento NO coincide entre la cédula y el formulario.",
                    valor_formulario=str(form_tipo),
                    valor_documento=str(doc_tipo),
                ))

        # --- Fecha de nacimiento ---
        # La cédula usa DD-MMM-AAAA (ej: "01-SEP-1995"); el formulario usa YYYY-MM-DD.
        # Se normalizan ambos a objeto date antes de comparar.
        doc_fn = datos.get("fecha_nacimiento")
        form_fn = form_data.get("fecha_nacimiento")
        if doc_fn and form_fn:
            fecha_doc  = parse_fecha(doc_fn)
            fecha_form = parse_fecha(form_fn)
            if fecha_doc and fecha_form:
                coincide = fecha_doc == fecha_form
                findings.append(
                    ValidationFinding.ok(
                        campo="fecha_nacimiento_cedula",
                        detalle="Fecha de nacimiento coincide con la cédula.",
                        valor_formulario=str(form_fn),
                        valor_documento=str(doc_fn),
                    ) if coincide else ValidationFinding.advertencia(
                        campo="fecha_nacimiento_cedula",
                        detalle="Fecha de nacimiento difiere entre la cédula y el formulario. Verifique.",
                        valor_formulario=str(form_fn),
                        valor_documento=str(doc_fn),
                    )
                )
            elif not fecha_doc or not fecha_form:
                # Si algún formato no es parseable, se deja como advertencia informativa
                findings.append(ValidationFinding.advertencia(
                    campo="fecha_nacimiento_cedula",
                    detalle="No se pudo comparar la fecha de nacimiento (formato no reconocido). Verifique manualmente.",
                    valor_formulario=str(form_fn),
                    valor_documento=str(doc_fn),
                ))

        return findings
