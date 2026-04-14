"""
Servicio encargado de interactuar con IA para la extracción y análisis de
documentos adjuntos, y detección de inconsistencias.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models import DocumentoAdjunto, Formulario
from core.contratos import AlertaInconsistencia, IExtractorIA
from services.formulario.prellenado import mapear_campos_para_formulario

from services.alertas.detector_inconsistencias_nombre import detector as _detector_nombres
from services.alertas.detector_inconsistencias_nit import detector as _detector_nit
from services.alertas.detector_inconsistencias_nombre_representante import detector as _detector_nombre_representante
from services.alertas.detector_inconsistencias_numero_doc_representante import detector as _detector_numero_doc_representante
from services.alertas.detector_inconsistencias_direccion import detector as _detector_direccion


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
    documento: DocumentoAdjunto
    campos_sugeridos: Dict[str, Any]
    razon_social_extraida: Optional[str]
    alerta_nombre: Optional[AlertaInconsistencia]
    nit_extraido: Optional[str] = None
    alerta_nit: Optional[AlertaInconsistencia] = None
    nombre_representante_extraido: Optional[str] = None
    alerta_nombre_representante: Optional[AlertaInconsistencia] = None
    numero_doc_representante_extraido: Optional[str] = None
    alerta_numero_doc_representante: Optional[AlertaInconsistencia] = None
    direccion_extraida: Optional[str] = None
    alerta_direccion: Optional[AlertaInconsistencia] = None


class AnalisisDocumentosService:
    """
    Orquesta la extracción de datos de documentos usando IA y los
    detectores de inconsistencias.
    """

    def __init__(self, extractor: IExtractorIA) -> None:
        self._extractor = extractor
        self._detector_nombres = _detector_nombres
        self._detector_nit = _detector_nit
        self._detector_nombre_representante = _detector_nombre_representante
        self._detector_numero_doc_representante = _detector_numero_doc_representante
        self._detector_direccion = _detector_direccion

    async def analizar_nueva_carga(
        self,
        documento: DocumentoAdjunto,
        formulario: Formulario
    ) -> ResultadoGuardadoDocumento:
        """
        Extrae datos del documento guardado y cruza contra los valores
        del formulario usando los detectores.
        """
        extraccion = await self._extractor.extraer(
            str(documento.ruta_archivo), documento.tipo_documento
        )

        campos_sugeridos: Dict[str, Any] = {}
        razon_social_extraida: Optional[str] = None
        alerta_nombre: Optional[AlertaInconsistencia] = None
        nit_extraido: Optional[str] = None
        alerta_nit: Optional[AlertaInconsistencia] = None
        nombre_representante_extraido: Optional[str] = None
        alerta_nombre_representante: Optional[AlertaInconsistencia] = None
        numero_doc_representante_extraido: Optional[str] = None
        alerta_numero_doc_representante: Optional[AlertaInconsistencia] = None
        direccion_extraida: Optional[str] = None
        alerta_direccion: Optional[AlertaInconsistencia] = None

        if extraccion.extraido:
            campos_sugeridos = mapear_campos_para_formulario(
                documento.tipo_documento, extraccion.datos
            )
            razon_social_extraida = self._detector_nombres.extraer_valor_de_documento(
                documento.tipo_documento, extraccion.datos
            )
            alerta_nombre = self._detector_nombres.detectar(
                tipo_documento=documento.tipo_documento,
                datos_extraidos=extraccion.datos,
                valor_formulario=formulario.razon_social,
            )
            nit_extraido = self._detector_nit.extraer_valor_de_documento(
                documento.tipo_documento, extraccion.datos
            )
            alerta_nit = self._detector_nit.detectar(
                tipo_documento=documento.tipo_documento,
                datos_extraidos=extraccion.datos,
                valor_formulario=formulario.numero_identificacion,
                tipo_identificacion_formulario=formulario.tipo_identificacion,
            )
            nombre_representante_extraido = self._detector_nombre_representante.extraer_valor_de_documento(
                documento.tipo_documento, extraccion.datos
            )
            alerta_nombre_representante = self._detector_nombre_representante.detectar(
                tipo_documento=documento.tipo_documento,
                datos_extraidos=extraccion.datos,
                valor_formulario=formulario.nombre_representante,
            )
            numero_doc_representante_extraido = self._detector_numero_doc_representante.extraer_valor_de_documento(
                documento.tipo_documento, extraccion.datos
            )
            alerta_numero_doc_representante = self._detector_numero_doc_representante.detectar(
                tipo_documento=documento.tipo_documento,
                datos_extraidos=extraccion.datos,
                valor_formulario=formulario.numero_doc_representante,
            )
            direccion_extraida = self._detector_direccion.extraer_valor_de_documento(
                documento.tipo_documento, extraccion.datos
            )
            alerta_direccion = self._detector_direccion.detectar(
                tipo_documento=documento.tipo_documento,
                datos_extraidos=extraccion.datos,
                valor_formulario=formulario.direccion,
            )

        return ResultadoGuardadoDocumento(
            documento=documento,
            campos_sugeridos=campos_sugeridos,
            razon_social_extraida=razon_social_extraida,
            alerta_nombre=alerta_nombre,
            nit_extraido=nit_extraido,
            alerta_nit=alerta_nit,
            nombre_representante_extraido=nombre_representante_extraido,
            alerta_nombre_representante=alerta_nombre_representante,
            numero_doc_representante_extraido=numero_doc_representante_extraido,
            alerta_numero_doc_representante=alerta_numero_doc_representante,
            direccion_extraida=direccion_extraida,
            alerta_direccion=alerta_direccion,
        )

    async def prellenar_documento(
        self, documento: DocumentoAdjunto
    ) -> Dict[str, Any]:
        """
        Escanea un documento individual y devuelve campos consolidados.
        """
        extraccion = await self._extractor.extraer(
            ruta_archivo=documento.ruta_archivo,
            tipo_documento=documento.tipo_documento,
        )
        if not extraccion.extraido:
            return {"success": False, "message": extraccion.mensaje, "campos_sugeridos": {}}

        return {
            "success": True,
            "message": extraccion.mensaje,
            "confianza": extraccion.confianza,
            "datos_extraidos": extraccion.datos,
            "campos_sugeridos": mapear_campos_para_formulario(
                documento.tipo_documento, extraccion.datos
            ),
        }

    async def prellenar_multiples_documentos(
        self, documentos: List[DocumentoAdjunto]
    ) -> Dict[str, Any]:
        """
        Escanea todos los envíos y extrae valores con AI.
        """
        campos_consolidados: Dict[str, Any] = {}
        detalles: List[Dict[str, Any]] = []

        for doc in documentos:
            extraccion = await self._extractor.extraer(
                ruta_archivo=doc.ruta_archivo,
                tipo_documento=doc.tipo_documento,
            )

            campos: Dict[str, Any] = {}
            if extraccion.extraido:
                campos = mapear_campos_para_formulario(doc.tipo_documento, extraccion.datos)
                for clave, valor in campos.items():
                    if clave not in campos_consolidados and valor is not None:
                        campos_consolidados[clave] = valor

            detalles.append({
                "documento":       doc.nombre_archivo,
                "tipo":            doc.tipo_documento,
                "extraido":        extraccion.extraido,
                "campos_sugeridos":campos,
                "confianza":       extraccion.confianza,
            })

        return {
            "success": True,
            "campos_consolidados":    campos_consolidados,
            "detalles_por_documento": detalles,
        }
