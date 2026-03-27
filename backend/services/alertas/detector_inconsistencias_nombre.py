"""
Detector de inconsistencias en nombre/razón social entre formulario y documentos.

Sabe exactamente en qué campo de cada tipo de documento reside el nombre
del titular, y genera una AlertaInconsistenciaNombre cuando el valor extraído
no coincide con el valor del formulario.

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si el nombre
                             de un documento es inconsistente con el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de documento = agregar una
                             entrada en _DOCUMENTOS_MONITOREADOS, sin tocar
                             la lógica de DetectorInconsistenciasNombre.
- D (Inversión de Dependencias): depende de ComparadorRazonSocial (abstracción),
                                 no de lógica de normalización directa.

DRY: la configuración de cada documento (qué campo, qué nombre legible, qué
     sección de referencia) vive en _DOCUMENTOS_MONITOREADOS como única fuente
     de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.alertas.comparador_razon_social import ComparadorRazonSocial


# ── Configuración declarativa de documentos monitoreados ─────────────────────
# OCP: agregar un doc = agregar una entrada. No modificar DetectorInconsistenciasNombre.

_DOCUMENTOS_MONITOREADOS: Dict[str, Dict[str, str]] = {
    "certificado_existencia": {
        "campo_nombre":      "razon_social",
        "nombre_legible":    "Revisa los documentos adjuntos",
        "seccion_referencia": (
            "NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Razón social"
        ),
    },
    "rut": {
        "campo_nombre":      "razon_social",
        "nombre_legible":    "RUT (Registro Único Tributario)",
        "seccion_referencia": "IDENTIFICACIÓN → campo 35. Razón social",
    },
    "estados_financieros": {
        "campo_nombre":      "razon_social",
        "nombre_legible":    "Estados Financieros",
        "seccion_referencia": "Encabezado del documento (razón social del emisor)",
    },
    "referencias_bancarias": {
        "campo_nombre":      "titular",
        "nombre_legible":    "Referencias Bancarias",
        "seccion_referencia": "Nombre del titular de la cuenta",
    },
}


# ── Objeto de valor (inmutable) ───────────────────────────────────────────────

@dataclass(frozen=True)
class AlertaInconsistenciaNombre:
    """
    Inconsistencia detectada entre el nombre del formulario y el de un documento.

    Immutable Value Object: no puede modificarse una vez creado.

    Attributes:
        tipo_documento:    Clave del tipo (ej. "certificado_existencia").
        nombre_documento:  Nombre legible del documento (ej. "Certificado de…").
        seccion_referencia: Ubicación exacta del campo dentro del documento.
        valor_formulario:  Razón social tal como aparece en el formulario.
        valor_documento:   Razón social tal como aparece en el documento.
        tipo_alerta:       Gravedad: "error".
        mensaje:           Descripción legible para el usuario final.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str   # "error"
    mensaje: str


# ── Detector ─────────────────────────────────────────────────────────────────

class DetectorInconsistenciasNombre:
    """
    Genera alertas cuando el nombre/razón social extraído de un documento
    no coincide con el ingresado en el formulario.

    Uso típico (dentro de FormularioService, tras la extracción IA):
        alerta = detector.detectar(tipo_documento, datos_extraidos, razon_social_form)

    SRP: única responsabilidad — producir o descartar una alerta de nombre.
    DIP: depende de ComparadorRazonSocial; el comparador puede sustituirse sin
         modificar esta clase.
    """

    def __init__(self) -> None:
        self._comparador = ComparadorRazonSocial()

    # ── API pública ───────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        razon_social_formulario: Optional[str],
    ) -> Optional[AlertaInconsistenciaNombre]:
        """
        Detecta si hay inconsistencia de nombre para el documento recién procesado.

        Args:
            tipo_documento:           Tipo del documento subido.
            datos_extraidos:          Campos crudos extraídos por IA.
            razon_social_formulario:  Razón social actual del formulario (puede
                                      ser None si aún no se ha diligenciado).

        Returns:
            AlertaInconsistenciaNombre si hay discrepancia, None si coinciden
            o si no hay datos suficientes para comparar.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config["campo_nombre"])
        resultado = self._comparador.comparar(razon_social_formulario, valor_documento)

        if resultado is None or resultado.coincide:
            return None

        return AlertaInconsistenciaNombre(
            tipo_documento=tipo_documento,
            nombre_documento=config["nombre_legible"],
            seccion_referencia=config["seccion_referencia"],
            valor_formulario=resultado.valor_formulario_original,
            valor_documento=resultado.valor_documento_original,
            tipo_alerta="error",
            mensaje=(
                f"La razón social en el formulario "
                f"(\"{resultado.valor_formulario_original}\") "
                f"no coincide con la encontrada en {config['nombre_legible']} "
                f"(\"{resultado.valor_documento_original}\")."
            ),
        )

    def extraer_nombre_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae el campo de nombre/razón social de un documento sin comparar.

        Usado para devolver razon_social_extraida al frontend, que la almacena
        para recomparar en tiempo real cuando el usuario edita el formulario.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo de nombre, o None si no aplica o no se extrajo.
        """
        config = _DOCUMENTOS_MONITOREADOS.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config["campo_nombre"]) or None

    @staticmethod
    def tipos_monitoreados() -> List[str]:
        """Retorna los tipos de documento que generan alertas de nombre."""
        return list(_DOCUMENTOS_MONITOREADOS.keys())
