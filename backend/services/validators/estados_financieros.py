"""
Validador: Estados Financieros.

Alarmas:
- Activos / Pasivos / Patrimonio no coinciden con el formulario
- Estados financieros no son comparativos (2 años)
- Sin firma del representante legal
- Sin firma del revisor fiscal
- Unidad de cifras (miles, millones) puede causar discrepancias
"""

from datetime import datetime
from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding


class EstadosFinancierosValidator:
    """Valida estados financieros contra datos del formulario."""

    # Tolerancia del 5% por redondeo o diferencia de unidades
    TOLERANCE_PERCENT = 0.05

    @property
    def document_type(self) -> str:
        return "estados_financieros"

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        if not extracted_data.extraido:
            return [ValidationFinding(
                resultado="advertencia",
                campo="estados_financieros",
                detalle=f"No se pudieron extraer datos. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Factor de conversión según unidad ---
        factor = self._get_factor(datos.get("cifras_en", "pesos"))

        # --- Comparar cifras financieras ---
        comparisons = [
            ("total_activos", "Total Activos"),
            ("total_pasivos", "Total Pasivos"),
            ("patrimonio", "Patrimonio"),
        ]

        for campo, nombre in comparisons:
            finding = self._compare_amount(
                doc_value=datos.get(campo),
                form_value=form_data.get(campo),
                factor=factor,
                campo=campo,
                nombre=nombre,
            )
            if finding:
                findings.append(finding)

        # --- Verificar que sean comparativos (2 años) ---
        if datos.get("tiene_comparativo") is False:
            findings.append(ValidationFinding(
                resultado="error",
                campo="eeff_comparativo",
                detalle="Los estados financieros NO son comparativos. Deben incluir datos de 2 años.",
            ))
        elif datos.get("tiene_comparativo") is True:
            findings.append(ValidationFinding(
                resultado="ok",
                campo="eeff_comparativo",
                detalle="Estados financieros son comparativos (2 años).",
            ))

        # --- Verificar firma ---
        if datos.get("firmado") is False:
            findings.append(ValidationFinding(
                resultado="error",
                campo="eeff_firma",
                detalle="Los estados financieros NO están firmados.",
            ))

        # --- Verificar firma revisor fiscal ---
        if datos.get("firma_revisor_fiscal") is False:
            findings.append(ValidationFinding(
                resultado="advertencia",
                campo="eeff_revisor_fiscal",
                detalle="No se detecta firma del revisor fiscal en los estados financieros.",
            ))

        # --- Verificar año del reporte ---
        anio = datos.get("anio_reporte")
        if anio:
            anio_esperado = datetime.now().year - 1
            if int(anio) < anio_esperado:
                findings.append(ValidationFinding(
                    resultado="error",
                    campo="eeff_anio",
                    detalle=f"Estados financieros son del año {anio}. Se esperan del {anio_esperado}.",
                    valor_documento=str(anio),
                ))

        return findings

    def _compare_amount(
        self,
        doc_value: Any,
        form_value: Any,
        factor: float,
        campo: str,
        nombre: str,
    ) -> ValidationFinding | None:
        """Compara montos con tolerancia y factor de conversión."""
        if doc_value is None or form_value is None:
            return None

        try:
            val_doc = float(doc_value) * factor
            val_form = float(form_value)
            diff = abs(val_doc - val_form)
            tolerance = abs(val_doc) * self.TOLERANCE_PERCENT if val_doc != 0 else 0

            if diff > tolerance:
                return ValidationFinding(
                    resultado="error",
                    campo=campo,
                    detalle=f"{nombre} NO coincide. Diferencia: ${diff:,.0f} COP",
                    valor_formulario=f"${val_form:,.0f}",
                    valor_documento=f"${val_doc:,.0f}",
                )
            return ValidationFinding(
                resultado="ok",
                campo=campo,
                detalle=f"{nombre} coincide.",
                valor_formulario=f"${val_form:,.0f}",
                valor_documento=f"${val_doc:,.0f}",
            )
        except (ValueError, TypeError):
            return ValidationFinding(
                resultado="advertencia",
                campo=campo,
                detalle=f"No se pudo comparar {nombre}: valores no numéricos.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            )

    @staticmethod
    def _get_factor(cifras_en: str) -> float:
        """Factor de conversión según la unidad reportada."""
        mapping = {
            "pesos": 1.0,
            "miles": 1_000.0,
            "millones": 1_000_000.0,
        }
        return mapping.get(cifras_en.lower().strip(), 1.0) if cifras_en else 1.0
