"""
Validador: Certificado de Existencia y Representación Legal (Cámara de Comercio).

Alarmas que implementa:
- Razón social no coincide entre el certificado y el formulario
- NIT no coincide
- Representante legal no coincide
- Cédula del representante no coincide
- Certificado con más de 30 días de antigüedad
"""

from typing import Any, Dict, List, Optional

from services.contracts import HallazgoValidacion, ResultadoExtraccion
from services.validators._utils import (
    comparar_identificacion,
    comparar_texto,
    verificar_vigencia,
)


class ValidadorCamaraComercio:
    """
    Valida el Certificado de Existencia y Representación Legal
    contra los datos diligenciados en el formulario.

    SRP : única responsabilidad — contrastar datos del certificado vs formulario.
    OCP : extensible con nuevas reglas sin modificar las existentes.
    LSP : intercambiable con cualquier IValidadorDocumento sin romper el orquestador.
    """

    FUENTE = "certificado de Cámara de Comercio"

    @property
    def tipo_documento(self) -> str:
        return "certificado_existencia"

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Ejecuta todas las reglas de validación del certificado de Cámara de Comercio.

        Args:
            datos_extraidos:   Resultado de la extracción IA del documento.
            datos_formulario:  Datos ingresados por el usuario en el formulario.

        Returns:
            Lista de hallazgos (ok / error / advertencia).
        """
        if not datos_extraidos.extraido:
            return [HallazgoValidacion.advertencia(
                campo="certificado_existencia",
                detalle=f"No se pudieron extraer datos del certificado. {datos_extraidos.mensaje}",
            )]

        hallazgos: List[Optional[HallazgoValidacion]] = []
        datos = datos_extraidos.datos

        hallazgos.append(comparar_texto(
            valor_doc=datos.get("razon_social"),
            valor_form=datos_formulario.get("razon_social"),
            campo="razon_social",
            nombre="Razón social",
            fuente=self.FUENTE,
        ))

        hallazgos.append(comparar_identificacion(
            valor_doc=datos.get("nit"),
            valor_form=datos_formulario.get("numero_identificacion"),
            campo="numero_identificacion",
            nombre="NIT",
            fuente=self.FUENTE,
        ))

        hallazgos.append(comparar_texto(
            valor_doc=datos.get("representante_legal"),
            valor_form=datos_formulario.get("nombre_representante"),
            campo="nombre_representante",
            nombre="Representante legal",
            fuente=self.FUENTE,
        ))

        hallazgos.append(comparar_identificacion(
            valor_doc=datos.get("cedula_representante"),
            valor_form=datos_formulario.get("numero_doc_representante"),
            campo="numero_doc_representante",
            nombre="Cédula del representante",
            fuente=self.FUENTE,
        ))

        hallazgos.append(verificar_vigencia(
            datos.get("fecha_documento"),
            campo="fecha_certificado_camara",
        ))

        return [h for h in hallazgos if h is not None]
