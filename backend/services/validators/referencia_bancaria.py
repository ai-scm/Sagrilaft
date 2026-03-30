"""
Validador: Referencia Bancaria.

Alarmas que implementa:
- Titular de la cuenta no coincide con la razón social del formulario
- Certificación bancaria con más de 30 días de antigüedad
"""

from typing import Any, Dict, List, Optional

from core.contracts import HallazgoValidacion, ResultadoExtraccion
from services.validators._utils import comparar_texto, verificar_vigencia


class ValidadorReferenciaBancaria:
    """
    Valida la referencia o certificación bancaria contra los datos del formulario.

    SRP : única responsabilidad — contrastar datos de la referencia vs formulario.
    OCP : extensible con nuevas reglas sin modificar las existentes.
    LSP : intercambiable con cualquier IValidadorDocumento sin romper el orquestador.
    """

    FUENTE = "referencia bancaria"

    @property
    def tipo_documento(self) -> str:
        return "referencias_bancarias"

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Ejecuta todas las reglas de validación de la referencia bancaria.

        Args:
            datos_extraidos:   Resultado de la extracción IA del documento.
            datos_formulario:  Datos ingresados por el usuario en el formulario.

        Returns:
            Lista de hallazgos (ok / error / advertencia).
        """
        if not datos_extraidos.extraido:
            return [HallazgoValidacion.advertencia(
                campo="referencia_bancaria",
                detalle=f"No se pudieron extraer datos. {datos_extraidos.mensaje}",
            )]

        hallazgos: List[Optional[HallazgoValidacion]] = []
        datos = datos_extraidos.datos

        hallazgos.append(self._validar_titular(datos, datos_formulario))
        hallazgos.append(verificar_vigencia(
            datos.get("fecha_documento"),
            campo="fecha_ref_bancaria",
        ))

        return [h for h in hallazgos if h is not None]

    # ─── Reglas de validación privadas ───────────────────────────────────────

    def _validar_titular(
        self,
        datos: Dict[str, Any],
        datos_formulario: Dict[str, Any],
    ) -> Optional[HallazgoValidacion]:
        """Compara el titular de la cuenta bancaria con la razón social del formulario."""
        return comparar_texto(
            valor_doc=datos.get("titular"),
            valor_form=datos_formulario.get("razon_social"),
            campo="titular_banco",
            nombre="Titular de la cuenta",
            fuente=self.FUENTE,
        )
