"""
Validador: Cédula del Representante Legal.

Alarmas que implementa:
- Nombre no coincide con el formulario
- Número de documento no coincide
- Tipo de documento no coincide
- Fecha de nacimiento difiere entre cédula y formulario
"""

from typing import Any, Dict, List, Optional

from core.contratos import HallazgoValidacion, ResultadoExtraccion
from services.validators._utils import (
    comparar_identificacion,
    comparar_texto,
    parsear_fecha,
)


class ValidadorCedula:
    """
    Valida la cédula del representante legal contra los datos del formulario.

    SRP : única responsabilidad — contrastar datos de la cédula vs formulario.
    OCP : extensible con nuevas reglas sin modificar las existentes.
    LSP : intercambiable con cualquier IValidadorDocumento sin romper el orquestador.
    """

    FUENTE = "cédula del representante"

    @property
    def tipo_documento(self) -> str:
        return "cedula_representante"

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Ejecuta todas las reglas de validación de la cédula.

        Args:
            datos_extraidos:   Resultado de la extracción IA del documento.
            datos_formulario:  Datos ingresados por el usuario en el formulario.

        Returns:
            Lista de hallazgos (ok / error / advertencia).
        """
        if not datos_extraidos.extraido:
            return [HallazgoValidacion.advertencia(
                campo="cedula_representante",
                detalle=f"No se pudieron extraer datos de la cédula. {datos_extraidos.mensaje}",
            )]

        hallazgos: List[Optional[HallazgoValidacion]] = []
        datos = datos_extraidos.datos

        hallazgos.append(self._validar_nombre(datos, datos_formulario))
        hallazgos.append(self._validar_numero_documento(datos, datos_formulario))
        hallazgos.append(self._validar_tipo_documento(datos, datos_formulario))
        hallazgos.append(self._validar_fecha_nacimiento(datos, datos_formulario))

        return [h for h in hallazgos if h is not None]

    # ─── Reglas de validación privadas ───────────────────────────────────────

    def _validar_nombre(
        self,
        datos: Dict[str, Any],
        datos_formulario: Dict[str, Any],
    ) -> Optional[HallazgoValidacion]:
        """Compara el nombre del representante entre la cédula y el formulario."""
        return comparar_texto(
            valor_doc=datos.get("nombre"),
            valor_form=datos_formulario.get("nombre_representante"),
            campo="nombre_representante_cedula",
            nombre="Nombre del representante",
            fuente=self.FUENTE,
        )

    def _validar_numero_documento(
        self,
        datos: Dict[str, Any],
        datos_formulario: Dict[str, Any],
    ) -> Optional[HallazgoValidacion]:
        """Compara el número de documento entre la cédula y el formulario."""
        return comparar_identificacion(
            valor_doc=datos.get("numero_documento"),
            valor_form=datos_formulario.get("numero_doc_representante"),
            campo="numero_doc_representante_cedula",
            nombre="Número de cédula",
            fuente=self.FUENTE,
        )

    @staticmethod
    def _validar_tipo_documento(
        datos: Dict[str, Any],
        datos_formulario: Dict[str, Any],
    ) -> Optional[HallazgoValidacion]:
        """
        Verifica que el tipo de documento de la cédula coincida con el formulario.
        Solo genera hallazgo cuando hay discrepancia (no se emite ok para este campo).
        """
        tipo_doc = datos.get("tipo_documento")
        tipo_formulario = datos_formulario.get("tipo_doc_representante")
        if not tipo_doc or not tipo_formulario:
            return None

        return comparar_texto(
            valor_doc=tipo_doc,
            valor_form=tipo_formulario,
            campo="tipo_doc_representante_cedula",
            nombre="Tipo de documento",
            fuente="cédula del representante",
        )

    @staticmethod
    def _validar_fecha_nacimiento(
        datos: Dict[str, Any],
        datos_formulario: Dict[str, Any],
    ) -> Optional[HallazgoValidacion]:
        """
        Compara la fecha de nacimiento entre la cédula y el formulario.

        La cédula usa formato DD-MMM-AAAA (ej: '01-SEP-1995');
        el formulario usa YYYY-MM-DD. Ambas se normalizan a `date` antes
        de comparar para evitar falsos negativos por diferencia de formato.
        """
        fecha_en_doc = datos.get("fecha_nacimiento")
        fecha_en_formulario = datos_formulario.get("fecha_nacimiento")

        if not fecha_en_doc or not fecha_en_formulario:
            return None

        fecha_doc = parsear_fecha(fecha_en_doc)
        fecha_formulario = parsear_fecha(fecha_en_formulario)

        if fecha_doc and fecha_formulario:
            coincide = fecha_doc == fecha_formulario
            return (
                HallazgoValidacion.ok(
                    campo="fecha_nacimiento_cedula",
                    detalle="Fecha de nacimiento coincide con la cédula.",
                    valor_formulario=str(fecha_en_formulario),
                    valor_documento=str(fecha_en_doc),
                ) if coincide else HallazgoValidacion.advertencia(
                    campo="fecha_nacimiento_cedula",
                    detalle="Fecha de nacimiento difiere entre la cédula y el formulario. Verifique.",
                    valor_formulario=str(fecha_en_formulario),
                    valor_documento=str(fecha_en_doc),
                )
            )

        return HallazgoValidacion.advertencia(
            campo="fecha_nacimiento_cedula",
            detalle="No se pudo comparar la fecha de nacimiento (formato no reconocido). Verifique manualmente.",
            valor_formulario=str(fecha_en_formulario),
            valor_documento=str(fecha_en_doc),
        )
