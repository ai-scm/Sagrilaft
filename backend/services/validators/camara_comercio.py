"""
Validador: Certificado de Existencia y Representación Legal (Cámara de Comercio).

Alarmas que implementa:
- Razón social no coincide
- NIT no coincide
- Representante legal no coincide
- Cédula del representante no coincide
- Certificado con más de 30 días
"""

from datetime import datetime
from typing import Any, Dict, List

from services.contracts import ExtractionResult, ValidationFinding


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
            return [ValidationFinding(
                resultado="advertencia",
                campo="certificado_existencia",
                detalle=f"No se pudieron extraer datos. {extracted_data.mensaje}",
            )]

        findings: List[ValidationFinding] = []
        datos = extracted_data.datos

        # --- Razón social ---
        findings.append(self._compare_text(
            datos.get("razon_social"),
            form_data.get("razon_social"),
            campo="razon_social",
            nombre="Razón social",
            source="certificado de Cámara de Comercio",
        ))

        # --- NIT ---
        findings.append(self._compare_nit(
            datos.get("nit"),
            form_data.get("numero_identificacion"),
        ))

        # --- Representante legal ---
        findings.append(self._compare_text(
            datos.get("representante_legal"),
            form_data.get("nombre_representante"),
            campo="nombre_representante",
            nombre="Representante legal",
            source="certificado de Cámara de Comercio",
        ))

        # --- Cédula del representante ---
        findings.append(self._compare_nit(
            datos.get("cedula_representante"),
            form_data.get("numero_doc_representante"),
            campo="numero_doc_representante",
            nombre="Cédula del representante",
        ))

        # --- Vigencia del certificado (≤ 30 días) ---
        finding_fecha = self._check_vigencia(datos.get("fecha_documento"))
        if finding_fecha:
            findings.append(finding_fecha)

        return [f for f in findings if f is not None]

    # ── Helpers privados ──────────────────────────────────

    @staticmethod
    def _normalize(value: str) -> str:
        return value.lower().strip() if value else ""

    @staticmethod
    def _normalize_nit(value: str) -> str:
        if not value:
            return ""
        return str(value).replace(".", "").replace("-", "").replace(" ", "").strip()

    def _compare_text(
        self,
        doc_value: Any,
        form_value: Any,
        campo: str,
        nombre: str,
        source: str,
    ) -> ValidationFinding | None:
        if not doc_value or not form_value:
            return None

        if self._normalize(str(doc_value)) == self._normalize(str(form_value)):
            return ValidationFinding(
                resultado="ok", campo=campo,
                detalle=f"{nombre} coincide con {source}.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            )
        return ValidationFinding(
            resultado="error", campo=campo,
            detalle=f"{nombre} NO coincide entre {source} y el formulario.",
            valor_formulario=str(form_value),
            valor_documento=str(doc_value),
        )

    def _compare_nit(
        self,
        doc_value: Any,
        form_value: Any,
        campo: str = "numero_identificacion",
        nombre: str = "NIT",
    ) -> ValidationFinding | None:
        if not doc_value or not form_value:
            return None

        doc_clean = self._normalize_nit(str(doc_value))
        form_clean = self._normalize_nit(str(form_value))

        if doc_clean == form_clean:
            return ValidationFinding(
                resultado="ok", campo=campo,
                detalle=f"{nombre} coincide.",
                valor_formulario=str(form_value),
                valor_documento=str(doc_value),
            )
        return ValidationFinding(
            resultado="error", campo=campo,
            detalle=f"{nombre} NO coincide entre el certificado y el formulario.",
            valor_formulario=str(form_value),
            valor_documento=str(doc_value),
        )

    @staticmethod
    def _check_vigencia(fecha_str: Any) -> ValidationFinding | None:
        if not fecha_str:
            return None
        try:
            fecha = datetime.strptime(str(fecha_str), "%Y-%m-%d")
            dias = (datetime.now() - fecha).days
            if dias > 30:
                return ValidationFinding(
                    resultado="error",
                    campo="fecha_certificado_camara",
                    detalle=f"Certificado tiene {dias} días. NO debe superar 30 días.",
                    valor_documento=str(fecha_str),
                )
            return ValidationFinding(
                resultado="ok",
                campo="fecha_certificado_camara",
                detalle=f"Certificado vigente ({dias} días).",
                valor_documento=str(fecha_str),
            )
        except ValueError:
            return None
