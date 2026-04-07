"""
Validador: Estados Financieros.

Alarmas que implementa:
- Activos / Pasivos / Patrimonio no coinciden con el formulario
- Estados financieros no son comparativos (2 años)
- Sin firma del representante legal
- Sin firma del revisor fiscal
- Año del reporte desactualizado
- Unidad de cifras (miles, millones) puede causar discrepancias
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.contratos import HallazgoValidacion, ResultadoExtraccion


# ─── Constantes ──────────────────────────────────────────────────────────────

_FACTOR_POR_UNIDAD: Dict[str, float] = {
    "pesos": 1.0,
    "miles": 1_000.0,
    "millones": 1_000_000.0,
}

_CIFRAS_FINANCIERAS: List[Tuple[str, str]] = [
    ("total_activos", "Total Activos"),
    ("total_pasivos", "Total Pasivos"),
    ("patrimonio",    "Patrimonio"),
]


class ValidadorEstadosFinancieros:
    """
    Valida los estados financieros contra los datos diligenciados en el formulario.

    SRP : cada regla de negocio está aislada en su propio método privado.
    OCP : se extiende con nuevas reglas añadiendo métodos, sin tocar los existentes.
    LSP : intercambiable con cualquier IValidadorDocumento sin romper el orquestador.
    """

    TOLERANCIA_PORCENTUAL: float = 0.05  # 5 % de margen por redondeo o diferencia de unidades

    @property
    def tipo_documento(self) -> str:
        return "estados_financieros"

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """
        Ejecuta todas las reglas de validación de los estados financieros.

        Args:
            datos_extraidos:   Resultado de la extracción IA del documento.
            datos_formulario:  Datos ingresados por el usuario en el formulario.

        Returns:
            Lista de hallazgos (ok / error / advertencia).
        """
        if not datos_extraidos.extraido:
            return [HallazgoValidacion.advertencia(
                campo="estados_financieros",
                detalle=f"No se pudieron extraer datos. {datos_extraidos.mensaje}",
            )]

        hallazgos: List[Optional[HallazgoValidacion]] = []
        datos = datos_extraidos.datos

        factor_conversion = _obtener_factor(datos.get("cifras_en", "pesos"))

        for campo, nombre in _CIFRAS_FINANCIERAS:
            hallazgos.append(self._comparar_monto(
                valor_doc=datos.get(campo),
                valor_form=datos_formulario.get(campo),
                factor=factor_conversion,
                campo=campo,
                nombre=nombre,
            ))

        hallazgos.append(_validar_comparativo(datos.get("tiene_comparativo")))
        hallazgos.append(_validar_firma(datos.get("firmado")))
        hallazgos.append(_validar_firma_revisor(datos.get("firma_revisor_fiscal")))
        hallazgos.append(_validar_anio(datos.get("anio_reporte")))

        return [h for h in hallazgos if h is not None]

    # ─── Comparación de montos ────────────────────────────────────────────────

    def _comparar_monto(
        self,
        valor_doc: Any,
        valor_form: Any,
        factor: float,
        campo: str,
        nombre: str,
    ) -> Optional[HallazgoValidacion]:
        """
        Compara un monto financiero del documento contra el formulario,
        aplicando factor de conversión de unidades y tolerancia porcentual.

        Args:
            valor_doc:  Valor extraído del documento (puede estar en miles/millones).
            valor_form: Valor ingresado en el formulario (en pesos).
            factor:     Multiplicador para convertir a pesos.
            campo:      Nombre del campo para el hallazgo.
            nombre:     Nombre legible del campo (ej. "Total Activos").

        Returns:
            HallazgoValidacion con ok/error/advertencia, o None si algún valor es nulo.
        """
        if valor_doc is None or valor_form is None:
            return None

        try:
            monto_doc = float(valor_doc) * factor
            monto_formulario = float(valor_form)
            diferencia = abs(monto_doc - monto_formulario)
            tolerancia = abs(monto_doc) * self.TOLERANCIA_PORCENTUAL if monto_doc != 0 else 0

            if diferencia > tolerancia:
                return HallazgoValidacion.error(
                    campo=campo,
                    detalle=f"{nombre} NO coincide. Diferencia: ${diferencia:,.0f} COP",
                    valor_formulario=f"${monto_formulario:,.0f}",
                    valor_documento=f"${monto_doc:,.0f}",
                )
            return HallazgoValidacion.ok(
                campo=campo,
                detalle=f"{nombre} coincide.",
                valor_formulario=f"${monto_formulario:,.0f}",
                valor_documento=f"${monto_doc:,.0f}",
            )
        except (ValueError, TypeError):
            return HallazgoValidacion.advertencia(
                campo=campo,
                detalle=f"No se pudo comparar {nombre}: valores no numéricos.",
                valor_formulario=str(valor_form),
                valor_documento=str(valor_doc),
            )


# ─── Reglas de validación independientes (funciones puras) ───────────────────
# Se definen fuera de la clase porque no dependen del estado del objeto
# y son potencialmente reutilizables por otros validadores.

def _obtener_factor(cifras_en: str) -> float:
    """
    Retorna el multiplicador necesario para convertir la unidad
    reportada en los estados financieros a pesos colombianos.

    Args:
        cifras_en: Unidad del documento ('pesos', 'miles', 'millones').

    Returns:
        Factor de conversión (1.0, 1_000.0 o 1_000_000.0).
    """
    if not cifras_en:
        return 1.0
    return _FACTOR_POR_UNIDAD.get(cifras_en.lower().strip(), 1.0)


def _validar_comparativo(tiene_comparativo: Optional[bool]) -> Optional[HallazgoValidacion]:
    """Verifica que los estados financieros incluyan datos de 2 años."""
    if tiene_comparativo is False:
        return HallazgoValidacion.error(
            campo="eeff_comparativo",
            detalle="Los estados financieros NO son comparativos. Deben incluir datos de 2 años.",
        )
    if tiene_comparativo is True:
        return HallazgoValidacion.ok(
            campo="eeff_comparativo",
            detalle="Estados financieros son comparativos (2 años).",
        )
    return None


def _validar_firma(firmado: Optional[bool]) -> Optional[HallazgoValidacion]:
    """Verifica que los estados financieros estén firmados por el representante legal."""
    if firmado is False:
        return HallazgoValidacion.error(
            campo="eeff_firma",
            detalle="Los estados financieros NO están firmados.",
        )
    return None


def _validar_firma_revisor(firma_revisor_fiscal: Optional[bool]) -> Optional[HallazgoValidacion]:
    """Verifica que los estados financieros tengan firma del revisor fiscal."""
    if firma_revisor_fiscal is False:
        return HallazgoValidacion.advertencia(
            campo="eeff_revisor_fiscal",
            detalle="No se detecta firma del revisor fiscal en los estados financieros.",
        )
    return None


def _validar_anio(anio_reporte: Optional[Any]) -> Optional[HallazgoValidacion]:
    """
    Verifica que el año de los estados financieros sea el inmediatamente anterior
    al año en curso (ej. en 2025 se esperan estados del 2024).
    """
    if not anio_reporte:
        return None

    anio_esperado = datetime.now().year - 1
    if int(anio_reporte) < anio_esperado:
        return HallazgoValidacion.error(
            campo="eeff_anio",
            detalle=(
                f"Estados financieros son del año {anio_reporte}. "
                f"Se esperan del {anio_esperado}."
            ),
            valor_documento=str(anio_reporte),
        )
    return None
