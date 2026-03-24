"""
Validador: RUT (Registro Único Tributario).

Alarmas:
- Razón social no coincide
- NIT no coincide
- Actividades económicas no coinciden con CIIU del formulario
- RUT no es del año vigente
"""

from datetime import datetime
from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding


class RutValidator:
    """Valida RUT contra datos del formulario."""

    @property
    def document_type(self) -> str:
        return "rut"

    def validate(
        self,
        extracted_data: ExtractionResult,
        form_data: Dict[str, Any],
    ) -> List[ValidationFinding]:
        if not extracted_data.extraido:
            return [ValidationFinding(
                resultado="advertencia",
                campo="rut",
                detalle=f"No se pudieron extraer datos del RUT. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Razón social ---
        findings.append(self._compare_text(
            datos.get("razon_social"),
            form_data.get("razon_social"),
            campo="razon_social_rut",
            nombre="Razón social",
        ))

        # --- NIT ---
        findings.append(self._compare_nit(
            datos.get("nit"),
            form_data.get("numero_identificacion"),
        ))

        # --- Actividades económicas vs CIIU ---
        actividades = datos.get("actividades_economicas", [])
        ciiu_form = form_data.get("codigo_ciiu")
        if actividades and ciiu_form:
            ciiu_encontrado = any(
                str(ciiu_form) in str(act) for act in actividades
            )
            findings.append(ValidationFinding(
                resultado="ok" if ciiu_encontrado else "advertencia",
                campo="codigo_ciiu",
                detalle=(
                    f"Código CIIU {ciiu_form} encontrado en RUT."
                    if ciiu_encontrado
                    else f"Código CIIU {ciiu_form} NO aparece en actividades del RUT: {', '.join(str(a) for a in actividades)}"
                ),
                valor_formulario=str(ciiu_form),
                valor_documento=", ".join(str(a) for a in actividades),
            ))

        # --- Año vigente ---
        fecha_doc = datos.get("fecha_documento")
        if fecha_doc:
            try:
                anio_doc = datetime.strptime(str(fecha_doc), "%Y-%m-%d").year
                anio_actual = datetime.now().year
                if anio_doc != anio_actual:
                    findings.append(ValidationFinding(
                        resultado="error",
                        campo="fecha_rut",
                        detalle=f"RUT es del año {anio_doc}. Debe ser del año en curso ({anio_actual}).",
                        valor_documento=str(fecha_doc),
                    ))
                else:
                    findings.append(ValidationFinding(
                        resultado="ok",
                        campo="fecha_rut",
                        detalle=f"RUT es del año vigente ({anio_actual}).",
                        valor_documento=str(fecha_doc),
                    ))
            except ValueError:
                pass

        return [f for f in findings if f is not None]

    @staticmethod
    def _compare_text(doc_val: Any, form_val: Any, campo: str, nombre: str) -> ValidationFinding | None:
        if not doc_val or not form_val:
            return None
        d = str(doc_val).lower().strip()
        f = str(form_val).lower().strip()
        if d == f:
            return ValidationFinding(
                resultado="ok", campo=campo,
                detalle=f"{nombre} coincide con el RUT.",
                valor_formulario=str(form_val), valor_documento=str(doc_val),
            )
        return ValidationFinding(
            resultado="error", campo=campo,
            detalle=f"{nombre} NO coincide entre el RUT y el formulario.",
            valor_formulario=str(form_val), valor_documento=str(doc_val),
        )

    @staticmethod
    def _compare_nit(doc_val: Any, form_val: Any) -> ValidationFinding | None:
        if not doc_val or not form_val:
            return None
        d = str(doc_val).replace(".", "").replace("-", "").strip()
        f = str(form_val).replace(".", "").replace("-", "").strip()
        if d == f:
            return ValidationFinding(
                resultado="ok", campo="nit_rut",
                detalle="NIT coincide con el RUT.",
                valor_formulario=str(form_val), valor_documento=str(doc_val),
            )
        return ValidationFinding(
            resultado="error", campo="nit_rut",
            detalle="NIT NO coincide entre el RUT y el formulario.",
            valor_formulario=str(form_val), valor_documento=str(doc_val),
        )
