"""
Detector genérico de inconsistencias entre formulario y documentos adjuntos.

Reemplaza los cinco detectores específicos anteriores:
  - DetectorInconsistenciasNombre
  - DetectorInconsistenciasNit
  - DetectorInconsistenciasNombreRepresentante
  - DetectorInconsistenciasNumeroDocRepresentante
  - DetectorInconsistenciasDireccion

Cada detector específico se obtiene instanciando esta clase con su configuración.
Los archivos individuales (detector_inconsistencias_nombre.py, etc.) siguen existiendo
como módulos de configuración que exponen una instancia pre-construida lista para usar.

SOLID:
- S (Responsabilidad Única): única responsabilidad — detectar si un campo concreto
                             de un documento es inconsistente con su contraparte
                             en el formulario.
- O (Abierto/Cerrado):       soportar un nuevo tipo de campo = instanciar con nueva
                             config. Soportar un nuevo documento = agregar entrada al
                             dict pasado al constructor. Sin tocar esta clase.
- D (Inversión de Dependencias): recibe normalizador y condicion_previa como callables
                                 inyectados; no importa implementaciones concretas.

DRY: la lógica de detección (buscar config → extraer campo → comparar → construir
     alerta) vive en un único lugar en lugar de repetirse en cinco archivos.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.contracts import AlertaInconsistencia
from services.alertas.comparador import Comparador


class DetectorInconsistencias:
    """
    Detecta inconsistencias entre un campo del formulario y el mismo campo
    extraído de documentos adjuntos.

    Uso:
        detector = DetectorInconsistencias(
            normalizador=normalizar_razon_social,
            documentos_monitoreados=_DOCUMENTOS,
            campo_clave="campo_nombre",
            plantilla_mensaje=(
                'La razón social en el formulario ("{valor_formulario}") '
                'no coincide con la encontrada en {nombre_legible} ("{valor_documento}").'
            ),
        )
        alerta = detector.detectar(tipo_documento, datos_extraidos, valor_formulario)
        valor  = detector.extraer_valor_de_documento(tipo_documento, datos_extraidos)

    Args:
        normalizador:            Función que convierte un valor crudo a su forma
                                 canónica para comparación.
        documentos_monitoreados: Mapa tipo_documento → dict con al menos las claves
                                 campo_clave, "nombre_legible" y "seccion_referencia".
        campo_clave:             Nombre de la clave dentro de cada config de documento
                                 que apunta al campo extraído (ej. "campo_nombre").
        plantilla_mensaje:       Cadena de formato con las variables {valor_formulario},
                                 {nombre_legible} y {valor_documento}.
        condicion_previa:        Callable opcional; recibe los **kwargs extra de detectar().
                                 Si retorna False, detectar() devuelve None sin comparar.
                                 Útil para restricciones contextuales como solo actuar
                                 cuando tipo_identificacion == "NIT".
    """

    def __init__(
        self,
        normalizador: Callable[[Any], str],
        documentos_monitoreados: Dict[str, Dict[str, str]],
        campo_clave: str,
        plantilla_mensaje: str,
        condicion_previa: Optional[Callable[..., bool]] = None,
    ) -> None:
        self._comparador = Comparador(normalizador)
        self._documentos = documentos_monitoreados
        self._campo_clave = campo_clave
        self._plantilla_mensaje = plantilla_mensaje
        self._condicion_previa = condicion_previa

    # ── API pública ──────────────────────────────────────────────────────────────

    def detectar(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        valor_formulario: Optional[str],
        **kwargs: Any,
    ) -> Optional[AlertaInconsistencia]:
        """
        Detecta si hay inconsistencia del campo monitoreado para el documento dado.

        Args:
            tipo_documento:   Tipo del documento subido.
            datos_extraidos:  Campos crudos extraídos por IA.
            valor_formulario: Valor actual del campo en el formulario.
            **kwargs:         Parámetros contextuales adicionales que se reenvían
                              a condicion_previa (ej. tipo_identificacion_formulario).

        Returns:
            AlertaInconsistencia si hay discrepancia, None si coinciden, si no hay
            datos suficientes para comparar, o si condicion_previa devuelve False.
        """
        if self._condicion_previa is not None and not self._condicion_previa(**kwargs):
            return None

        config = self._documentos.get(tipo_documento)
        if not config:
            return None

        valor_documento = datos_extraidos.get(config[self._campo_clave])
        resultado = self._comparador.comparar(valor_formulario, valor_documento)

        if resultado is None or resultado.coincide:
            return None

        return AlertaInconsistencia(
            tipo_documento=tipo_documento,
            nombre_documento=config["nombre_legible"],
            seccion_referencia=config["seccion_referencia"],
            valor_formulario=resultado.valor_formulario_original,
            valor_documento=resultado.valor_documento_original,
            tipo_alerta="error",
            mensaje=self._plantilla_mensaje.format(
                valor_formulario=resultado.valor_formulario_original,
                nombre_legible=config["nombre_legible"],
                valor_documento=resultado.valor_documento_original,
            ),
        )

    def extraer_valor_de_documento(
        self,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Optional[str]:
        """
        Extrae el valor del campo monitoreado de un documento sin comparar.

        Usado para devolver el valor extraído al frontend, que lo almacena
        para recomparar en tiempo real cuando el usuario edita el formulario.

        Args:
            tipo_documento:  Tipo del documento.
            datos_extraidos: Campos crudos extraídos por IA.

        Returns:
            Valor del campo, o None si el tipo de documento no está monitoreado
            o si el campo no se extrajo.
        """
        config = self._documentos.get(tipo_documento)
        if not config:
            return None
        return datos_extraidos.get(config[self._campo_clave]) or None

    def tipos_monitoreados(self) -> List[str]:
        """Retorna los tipos de documento que este detector monitorea."""
        return list(self._documentos.keys())
