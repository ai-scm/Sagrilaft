"""
Transformadores de dominio a schemas HTTP.

Responsabilidad única: convertir objetos de dominio (value objects, resultados
de servicio) en schemas Pydantic listos para transporte HTTP.

SRP : cada función convierte exactamente un tipo de objeto de dominio.
DIP : depende de contratos de dominio y schemas de transporte,
      no de implementaciones concretas de ningún servicio.
OCP : agregar un nuevo campo al DocumentoResponse no requiere modificar los
      transformadores existentes, solo extender construir_respuesta_documento.
"""

from typing import Optional

from schemas import AlertaInconsistenciaResponse, DocumentoResponse
from core.contracts import AlertaInconsistencia
from services.formulario.formulario_service import ResultadoGuardadoDocumento


def serializar_alerta(
    alerta: Optional[AlertaInconsistencia],
) -> Optional[AlertaInconsistenciaResponse]:
    """Convierte un AlertaInconsistencia de dominio al schema HTTP de transporte."""
    if not alerta:
        return None
    return AlertaInconsistenciaResponse(
        tipo_documento=alerta.tipo_documento,
        nombre_documento=alerta.nombre_documento,
        seccion_referencia=alerta.seccion_referencia,
        valor_formulario=alerta.valor_formulario,
        valor_documento=alerta.valor_documento,
        tipo_alerta=alerta.tipo_alerta,
        mensaje=alerta.mensaje,
    )


def construir_respuesta_documento(
    resultado: ResultadoGuardadoDocumento,
) -> DocumentoResponse:
    """Convierte un ResultadoGuardadoDocumento al schema HTTP DocumentoResponse."""
    doc = resultado.documento
    return DocumentoResponse(
        id=doc.id,
        tipo_documento=doc.tipo_documento,
        nombre_archivo=doc.nombre_archivo,
        content_type=doc.content_type,
        tamano=doc.tamano,
        created_at=doc.created_at,
        campos_sugeridos=resultado.campos_sugeridos or None,
        razon_social_extraida=resultado.razon_social_extraida,
        alerta_nombre=serializar_alerta(resultado.alerta_nombre),
        nit_extraido=resultado.nit_extraido,
        alerta_nit=serializar_alerta(resultado.alerta_nit),
        nombre_representante_extraido=resultado.nombre_representante_extraido,
        alerta_nombre_representante=serializar_alerta(resultado.alerta_nombre_representante),
        numero_doc_representante_extraido=resultado.numero_doc_representante_extraido,
        alerta_numero_doc_representante=serializar_alerta(resultado.alerta_numero_doc_representante),
        direccion_extraida=resultado.direccion_extraida,
        alerta_direccion=serializar_alerta(resultado.alerta_direccion),
    )
