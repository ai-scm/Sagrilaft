"""
Validador: RUT (Registro Único Tributario).

Alarmas que implementa:
- Razón social no coincide con el formulario
- NIT no coincide con el formulario
- Actividades económicas no coinciden con el CIIU del formulario
- RUT no es del año vigente
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from services.alertas.normalizador_nit import normalizar_nit
from core.contratos import HallazgoValidacion, ResultadoExtraccion
from services.validators._utils import (
    FORMATO_FECHA,
    comparar_identificacion,
    comparar_texto,
)


class ValidadorRut:
    """
    Valida el RUT (Registro Único Tributario) contra los datos
    diligenciados en el formulario.

    SRP : única responsabilidad — contrastar datos del RUT vs formulario.
    OCP : extensible con nuevas reglas sin modificar las existentes.
    LSP : intercambiable con cualquier ValidadorDocumentoImp sin romper el orquestador.
    """

    FUENTE = "RUT"

    @property
    def tipo_documento(self) -> str:
        return "rut"

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Ejecuta todas las reglas de validación del RUT.

        Args:
            datos_extraidos:   Resultado de la extracción IA del documento.
            datos_formulario:  Datos ingresados por el usuario en el formulario.

        Returns:
            Lista de hallazgos (ok / error / advertencia).
        """
        if not datos_extraidos.extraido:
            return [HallazgoValidacion.advertencia(
                campo="rut",
                detalle=f"No se pudieron extraer datos del RUT. {datos_extraidos.mensaje}",
            )]

        hallazgos: List[Optional[HallazgoValidacion]] = []
        datos = datos_extraidos.datos

        hallazgos.append(comparar_texto(
            valor_doc=datos.get("razon_social"),
            valor_form=datos_formulario.get("razon_social"),
            campo="razon_social_rut",
            nombre="Razón social",
            fuente=self.FUENTE,
        ))

        hallazgos.append(comparar_identificacion(
            valor_doc=datos.get("nit"),
            valor_form=datos_formulario.get("numero_identificacion"),
            campo="nit_rut",
            nombre="NIT",
            fuente=self.FUENTE,
            normalizador=normalizar_nit,
        ))

        hallazgos.append(_validar_ciiu(
            actividades=datos.get("actividades_economicas", []),
            ciiu_formulario=datos_formulario.get("codigo_ciiu"),
        ))

        hallazgos.append(_validar_anio_vigente(datos.get("fecha_documento")))

        return [h for h in hallazgos if h is not None]


# ─── Reglas de validación independientes (funciones puras) ───────────────────

def _validar_ciiu(
    actividades: List[Any],
    ciiu_formulario: Optional[str],
) -> Optional[HallazgoValidacion]:
    """
    Verifica que el código CIIU del formulario aparezca entre las
    actividades económicas registradas en el RUT.

    Args:
        actividades:      Lista de actividades económicas extraídas del RUT.
        ciiu_formulario:  Código CIIU ingresado por el usuario en el formulario.

    Returns:
        HallazgoValidacion ok/advertencia, o None si algún valor está ausente.
    """
    if not actividades or not ciiu_formulario:
        return None

    actividades_como_texto = ", ".join(str(a) for a in actividades)
    encontrado = any(str(ciiu_formulario) in str(act) for act in actividades)

    if encontrado:
        return HallazgoValidacion.ok(
            campo="codigo_ciiu",
            detalle=f"Código CIIU {ciiu_formulario} encontrado en RUT.",
            valor_formulario=str(ciiu_formulario),
            valor_documento=actividades_como_texto,
        )
    return HallazgoValidacion.advertencia(
        campo="codigo_ciiu",
        detalle=(
            f"Código CIIU {ciiu_formulario} NO aparece en actividades del RUT: "
            f"{actividades_como_texto}"
        ),
        valor_formulario=str(ciiu_formulario),
        valor_documento=actividades_como_texto,
    )


def _validar_anio_vigente(
    fecha_documento: Optional[Any],
) -> Optional[HallazgoValidacion]:
    """
    Verifica que el RUT sea del año en curso.

    Args:
        fecha_documento: Fecha del RUT en formato YYYY-MM-DD.

    Returns:
        HallazgoValidacion ok/error, o None si la fecha es nula o inválida.
    """
    if not fecha_documento:
        return None

    try:
        anio_doc = datetime.strptime(str(fecha_documento), FORMATO_FECHA).year
        anio_actual = datetime.now().year

        if anio_doc == anio_actual:
            return HallazgoValidacion.ok(
                campo="fecha_rut",
                detalle=f"RUT es del año vigente ({anio_actual}).",
                valor_documento=str(fecha_documento),
            )
        return HallazgoValidacion.error(
            campo="fecha_rut",
            detalle=f"RUT es del año {anio_doc}. Debe ser del año en curso ({anio_actual}).",
            valor_documento=str(fecha_documento),
        )
    except ValueError:
        return None
