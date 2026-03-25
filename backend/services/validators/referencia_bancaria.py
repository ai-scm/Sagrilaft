"""
Validador: Referencia Bancaria.

Alarmas:
- Titular no coincide con razón social
- Certificación bancaria con más de 30 días
"""

from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding
from services.validators._utils import check_vigencia, normalize_text


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
            return [ValidationFinding.advertencia(
                campo="referencia_bancaria",
                detalle=f"No se pudieron extraer datos. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Titular vs razón social ---
        titular = datos.get("titular")
        razon = form_data.get("razon_social")
        if titular and razon:
            coincide = normalize_text(titular) == normalize_text(razon)
            findings.append(
                ValidationFinding.ok(
                    campo="titular_banco",
                    detalle="Titular de la cuenta coincide con la razón social.",
                    valor_formulario=str(razon),
                    valor_documento=str(titular),
                ) if coincide else ValidationFinding.error(
                    campo="titular_banco",
                    detalle="Titular de la cuenta NO coincide con la razón social.",
                    valor_formulario=str(razon),
                    valor_documento=str(titular),
                )
            )

        # --- Vigencia (≤ 30 días) ---
        finding_fecha = check_vigencia(datos.get("fecha_documento"), campo="fecha_ref_bancaria")
        if finding_fecha:
            findings.append(finding_fecha)

        return findings
