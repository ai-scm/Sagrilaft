"""
Detector de inconsistencias en NIT entre formulario y documentos.

Sabe exactamente en qué campo de cada tipo de documento reside el NIT
del titular, y genera una AlertaInconsistenciaNit cuando el valor extraído
no coincide con el NIT registrado en el formulario.

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si el NIT
                             de un documento es inconsistente con el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de documento = agregar una
                             entrada en _DOCUMENTOS_MONITOREADOS_NIT, sin tocar
                             la lógica de DetectorInconsistenciasNit.
- D (Inversión de Dependencias): depende de Comparador (abstracción),
                                 no de lógica de normalización directa.

DRY: la configuración de cada documento (qué campo, qué nombre legible, qué
     sección de referencia) vive en _DOCUMENTOS_MONITOREADOS_NIT como única
     fuente de verdad.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.alertas.comparador import Comparador
from services.alertas.normalizador_nit import normalizar_nit
from services.contracts import AlertaInconsistencia


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistenciasNit.

_DOCUMENTOS_MONITOREADOS_NIT: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_nit":         "nit",
        "nombre_legible":    "Certificado de Existencia y Representación Legal",
        "seccion_referencia": (
            "NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Nit"
        ),
    },
    "rut": {
        "campo_nit":         "nit",
        "nombre_legible":    "RUT (Registro Único Tributario)",
        "seccion_referencia": (
            "IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)"
        ),
    },
    "estados_financieros": {
        "campo_nit":         "nit",
        "nombre_legible":    "Estados Financieros",
        "seccion_referencia": (
            "Encabezado o membrete del documento (NIT del emisor)"
        ),
    },
    "declaracion_renta": {
        "campo_nit":         "nit",
        "nombre_legible":    "Declaración de Renta",
        "seccion_referencia": (
            "IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)"
        ),
    },
    "referencias_bancarias": {
        "campo_nit":         "nit",
        "nombre_legible":    "Referencias Bancarias",
        "seccion_referencia": (
            "NIT del titular de la cuenta (si aparece en el documento)"
        ),
    },
}


# ── Detector ─────────────────────────────────────────────────────────────────

class DetectorInconsistenciasNit:
    """
    Genera alertas cuando el NIT extraído de un documento no coincide con el
    número de identificación registrado en el formulario.

    Solo actúa cuando el tipo de identificación del formulario es "NIT";
    si la contraparte usa cédula u otro tipo, no se emiten alertas de NIT.

    Uso típico (dentro de FormularioService, tras la extracción IA):
        alerta = detector.detectar(
            tipo_documento, datos_extraidos,
            numero_identificacion_form, tipo_identificacion_form
        )

    SRP: única responsabilidad — producir o descartar una alerta de NIT.
    DIP: depende de Comparador; el comparador puede sustituirse sin
         modificar esta clase.
    """

    def __init__(self) -> None:
        self._comparador = Comparador(normalizar_nit)

    # ── API pública ───────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        numero_identificacion_formulario: Optional[str],
        tipo_identificacion_formulario: Optional[str] = "NIT",
    ) -> Optional[AlertaInconsistencia]:
        """
        Detecta si hay inconsistencia de NIT para el documento recién procesado.

        Args:
            tipo_documento:                  Tipo del documento subido.
            datos_extraidos:                 Campos crudos extraídos por IA.
            numero_identificacion_formulario: NIT actual del formulario (puede
                                              ser None si aún no se ha diligenciado).
            tipo_identificacion_formulario:  Tipo de ID del formulario; la alerta
                                             solo se genera si es "NIT".

        Returns:
            AlertaInconsistenciaNit si hay discrepancia, None si coinciden,
            si no hay datos suficientes para comparar, o si el tipo de
            identificación no es NIT.
        """
        # Solo aplica cuando la contraparte tiene NIT
        if (tipo_identificacion_formulario or "").upper() != "NIT":
            return None

        config = _DOCUMENTOS_MONITOREADOS_NIT.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config["campo_nit"])
        resultado = self._comparador.comparar(
            numero_identificacion_formulario, valor_documento
        )

        if resultado is None or resultado.coincide:
            return None

        return AlertaInconsistencia(
            tipo_documento=tipo_documento,
            nombre_documento=config["nombre_legible"],
            seccion_referencia=config["seccion_referencia"],
            valor_formulario=resultado.valor_formulario_original,
            valor_documento=resultado.valor_documento_original,
            tipo_alerta="error",
            mensaje=(
                f"El NIT en el formulario "
                f"(\"{resultado.valor_formulario_original}\") "
                f"no coincide con el encontrado en {config['nombre_legible']} "
                f"(\"{resultado.valor_documento_original}\")."
            ),
        )

    def extraer_nit_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae el NIT de un documento sin comparar.

        Usado para devolver nit_extraido al frontend, que lo almacena
        para recomparar en tiempo real cuando el usuario edita el formulario.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo NIT, o None si no aplica o no se extrajo.
        """
        config = _DOCUMENTOS_MONITOREADOS_NIT.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config["campo_nit"]) or None

    @staticmethod
    def tipos_monitoreados() -> List[str]:
        """Retorna los tipos de documento que generan alertas de NIT."""
        return list(_DOCUMENTOS_MONITOREADOS_NIT.keys())
