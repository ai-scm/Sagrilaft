"""
Servicio encargado de interactuar con IA para la extracción y análisis de
documentos adjuntos, y detección de inconsistencias.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from models import DocumentoAdjunto, Formulario
from core.contratos import AlertaInconsistencia, ExtractorIAImp
from services.formulario.prellenado import mapear_campos_para_formulario

from services.alertas.detector_inconsistencias_nombre import detector as _detector_nombres
from services.alertas.detector_inconsistencias_nit import detector as _detector_nit
from services.alertas.detector_inconsistencias_nombre_representante import detector as _detector_nombre_representante
from services.alertas.detector_inconsistencias_numero_doc_representante import detector as _detector_numero_doc_representante
from services.alertas.detector_inconsistencias_direccion import detector as _detector_direccion


# ---------------------------------------------------------------------------
# Protocolo y configuración tipada
# ---------------------------------------------------------------------------

class IDetector(Protocol):
    def extraer_valor_de_documento(
        self, tipo_documento: str, datos: Dict[str, Any]
    ) -> Optional[str]: ...

    def detectar(
        self,
        *,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
        valor_formulario: Any,
        **kwargs: Any,
    ) -> Optional[AlertaInconsistencia]: ...


@dataclass
class ConfigDetector:
    campo_formulario: str
    detector:         IDetector
    attr_extraido:    str
    attr_alerta:      str
    get_extra_kwargs: Callable[[Formulario], Dict[str, Any]] = field(
        default_factory=lambda: lambda _: {}
    )


# ---------------------------------------------------------------------------
# DTO interno de extracción
# ---------------------------------------------------------------------------

@dataclass
class _ResultadoExtraccion:
    extraido:         bool
    datos:            Dict[str, Any] = field(default_factory=dict)
    campos_sugeridos: Dict[str, Any] = field(default_factory=dict)
    mensaje:          str            = ""
    confianza:        float          = 0.0


# ---------------------------------------------------------------------------
# Resultado público
# ---------------------------------------------------------------------------

@dataclass
class ResultadoGuardadoDocumento:
    """
    Encapsula el resultado de cargar y analizar un documento.

    Attributes:
        documento:                         Entidad ORM del documento persistido.
        campos_sugeridos:                  Campos del formulario sugeridos por la IA.
        razon_social_extraida:             Nombre/razón social encontrada en el documento.
        alerta_nombre:                     Alerta si el nombre del documento no coincide.
        nit_extraido:                      NIT encontrado en el documento.
        alerta_nit:                        Alerta si el NIT del documento no coincide.
        nombre_representante_extraido:     Nombre del represente legal encontrado en el documento.
        alerta_nombre_representante:       Alerta si el nombre del represente no coincide.
        numero_doc_representante_extraido: Número de documento del represente encontrado en el documento.
        alerta_numero_doc_representante:   Alerta si el número de documento del represente no coincide.
        direccion_extraida:                Dirección encontrada en el documento.
        alerta_direccion:                  Alerta si la dirección del documento no coincide.
    """
    documento:                         DocumentoAdjunto
    campos_sugeridos:                  Dict[str, Any]                 = field(default_factory=dict)
    razon_social_extraida:             Optional[str]                  = None
    alerta_nombre:                     Optional[AlertaInconsistencia] = None
    nit_extraido:                      Optional[str]                  = None
    alerta_nit:                        Optional[AlertaInconsistencia] = None
    nombre_representante_extraido:     Optional[str]                  = None
    alerta_nombre_representante:       Optional[AlertaInconsistencia] = None
    numero_doc_representante_extraido: Optional[str]                  = None
    alerta_numero_doc_representante:   Optional[AlertaInconsistencia] = None
    direccion_extraida:                Optional[str]                  = None
    alerta_direccion:                  Optional[AlertaInconsistencia] = None


# ---------------------------------------------------------------------------
# Configuración por defecto
# ---------------------------------------------------------------------------

def obtener_config_analisis_por_defecto() -> List[ConfigDetector]:
    """
    Devuelve la configuración estándar de detectores de inconsistencias.
    """
    return [
        ConfigDetector(
            campo_formulario = "razon_social",
            detector         = _detector_nombres,
            attr_extraido    = "razon_social_extraida",
            attr_alerta      = "alerta_nombre",
        ),
        ConfigDetector(
            campo_formulario = "numero_identificacion",
            detector         = _detector_nit,
            attr_extraido    = "nit_extraido",
            attr_alerta      = "alerta_nit",
            get_extra_kwargs = lambda f: {"tipo_identificacion_formulario": f.tipo_identificacion},
        ),
        ConfigDetector(
            campo_formulario = "nombre_representante",
            detector         = _detector_nombre_representante,
            attr_extraido    = "nombre_representante_extraido",
            attr_alerta      = "alerta_nombre_representante",
        ),
        ConfigDetector(
            campo_formulario = "numero_doc_representante",
            detector         = _detector_numero_doc_representante,
            attr_extraido    = "numero_doc_representante_extraido",
            attr_alerta      = "alerta_numero_doc_representante",
        ),
        ConfigDetector(
            campo_formulario = "direccion",
            detector         = _detector_direccion,
            attr_extraido    = "direccion_extraida",
            attr_alerta      = "alerta_direccion",
        ),
    ]


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------

class AnalisisDocumentosService:
    """
    Orquesta la extracción de datos de documentos usando IA y los
    detectores de inconsistencias.
    """

    def __init__(
        self, 
        extractor: ExtractorIAImp, 
        config_analisis: List[ConfigDetector]
    ) -> None:
        self._extractor = extractor
        self._config_analisis = config_analisis

    # -----------------------------------------------------------------------
    # Método privado compartido
    # -----------------------------------------------------------------------

    async def _extraer(self, documento: DocumentoAdjunto) -> _ResultadoExtraccion:
        """Extrae y mapea los datos de un documento. Punto único de entrada a la IA."""
        extraccion = await self._extractor.extraer(
            str(documento.ruta_archivo), documento.tipo_documento
        )
        if not extraccion.extraido:
            return _ResultadoExtraccion(
                extraido = False,
                mensaje  = extraccion.mensaje,
            )
        return _ResultadoExtraccion(
            extraido         = True,
            datos            = extraccion.datos,
            campos_sugeridos = mapear_campos_para_formulario(
                documento.tipo_documento, extraccion.datos
            ),
            mensaje          = extraccion.mensaje,
            confianza        = extraccion.confianza,
        )

    # -----------------------------------------------------------------------
    # Métodos públicos
    # -----------------------------------------------------------------------

    async def analizar_nueva_carga(
        self,
        documento: DocumentoAdjunto,
        formulario: Formulario,
    ) -> ResultadoGuardadoDocumento:
        """
        Extrae datos del documento guardado y cruza contra los valores
        del formulario usando los detectores.
        """
        extraccion = await self._extraer(documento)
        resultado  = ResultadoGuardadoDocumento(documento=documento)

        if not extraccion.extraido:
            return resultado

        resultado.campos_sugeridos = extraccion.campos_sugeridos

        for config in self._config_analisis:
            # 1. Extraer valor para el frontend
            setattr(
                resultado,
                config.attr_extraido,
                config.detector.extraer_valor_de_documento(
                    documento.tipo_documento, extraccion.datos
                ),
            )
            # 2. Detectar inconsistencias
            setattr(
                resultado,
                config.attr_alerta,
                config.detector.detectar(
                    tipo_documento   = documento.tipo_documento,
                    datos_extraidos  = extraccion.datos,
                    valor_formulario = getattr(formulario, config.campo_formulario),
                    **config.get_extra_kwargs(formulario),
                ),
            )

        return resultado

    async def prellenar_documento(
        self, documento: DocumentoAdjunto
    ) -> Dict[str, Any]:
        """
        Escanea un documento individual y devuelve campos consolidados.
        """
        extraccion = await self._extraer(documento)

        if not extraccion.extraido:
            return {"success": False, "message": extraccion.mensaje, "campos_sugeridos": {}}

        return {
            "success":          True,
            "message":          extraccion.mensaje,
            "confianza":        extraccion.confianza,
            "datos_extraidos":  extraccion.datos,
            "campos_sugeridos": extraccion.campos_sugeridos,
        }

    async def prellenar_multiples_documentos(
        self, documentos: List[DocumentoAdjunto]
    ) -> Dict[str, Any]:
        """
        Escanea todos los documentos y extrae valores con IA.
        """
        campos_consolidados: Dict[str, Any] = {}
        detalles: List[Dict[str, Any]]      = []

        for doc in documentos:
            extraccion = await self._extraer(doc)

            if extraccion.extraido:
                for clave, valor in extraccion.campos_sugeridos.items():
                    if clave not in campos_consolidados and valor is not None:
                        campos_consolidados[clave] = valor

            detalles.append({
                "documento":        doc.nombre_archivo,
                "tipo":             doc.tipo_documento,
                "extraido":         extraccion.extraido,
                "campos_sugeridos": extraccion.campos_sugeridos,
                "confianza":        extraccion.confianza,
            })

        return {
            "success":                True,
            "campos_consolidados":    campos_consolidados,
            "detalles_por_documento": detalles,
        }