"""
Validador: Referencia Bancaria.

Alarmas:
- Titular no coincide con razón social
- Certificación bancaria con más de 30 días
"""

from datetime import datetime
from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding


class ReferenciaBancariaValidator:
    """Valida referencia/certificación bancaria contra datos del formulario."""

    @property
    def document_type(self) -> str:
        return "referencias_bancarias"

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        if not extracted_data.extraido:
            return [ValidationFinding(
                resultado="advertencia",
                campo="referencia_bancaria",
                detalle=f"No se pudieron extraer datos. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Titular vs razón social ---
        titular = datos.get("titular")
        razon = form_data.get("razon_social")
        if titular and razon:
            if titular.lower().strip() == razon.lower().strip():
                findings.append(ValidationFinding(
                    resultado="ok",
                    campo="titular_banco",
                    detalle="Titular de la cuenta coincide con la razón social.",
                    valor_formulario=str(razon),
                    valor_documento=str(titular),
                ))
            else:
                findings.append(ValidationFinding(
                    resultado="error",
                    campo="titular_banco",
                    detalle="Titular de la cuenta NO coincide con la razón social.",
                    valor_formulario=str(razon),
                    valor_documento=str(titular),
                ))

        # --- Entidad bancaria ---
        entidad_doc = datos.get("entidad")
        entidad_form = form_data.get("entidad_bancaria")
        if entidad_doc and entidad_form:
            if entidad_doc.lower().strip() in entidad_form.lower().strip() or entidad_form.lower().strip() in entidad_doc.lower().strip():
                findings.append(ValidationFinding(
                    resultado="ok",
                    campo="entidad_bancaria",
                    detalle="Entidad bancaria coincide.",
                    valor_formulario=str(entidad_form),
                    valor_documento=str(entidad_doc),
                ))
            else:
                findings.append(ValidationFinding(
                    resultado="error",
                    campo="entidad_bancaria",
                    detalle="Entidad bancaria NO coincide entre la certificación y el formulario.",
                    valor_formulario=str(entidad_form),
                    valor_documento=str(entidad_doc),
                ))

        # --- Vigencia (≤ 30 días) ---
        fecha_str = datos.get("fecha_documento")
        if fecha_str:
            try:
                fecha = datetime.strptime(str(fecha_str), "%Y-%m-%d")
                dias = (datetime.now() - fecha).days
                if dias > 30:
                    findings.append(ValidationFinding(
                        resultado="error",
                        campo="fecha_ref_bancaria",
                        detalle=f"Certificación bancaria tiene {dias} días. NO debe superar 30 días.",
                        valor_documento=str(fecha_str),
                    ))
                else:
                    findings.append(ValidationFinding(
                        resultado="ok",
                        campo="fecha_ref_bancaria",
                        detalle=f"Certificación bancaria vigente ({dias} días).",
                        valor_documento=str(fecha_str),
                    ))
            except ValueError:
                pass

        return findings
