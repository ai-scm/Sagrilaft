"""
Utilidades para serialización y deserialización de estructuras complejas a JSON string.
Incluye conversores de entidades ORM a schemas de respuesta compartidos por
FormularioService y AccesoManualService.
"""

import json
from typing import Any, Dict, List
from schemas import DocumentoResponse
from infrastructure.persistencia.models import Formulario


# Campos que se almacenan como JSON string en la BD
_CAMPOS_JSON_ESCRITURA: List[str] = [
    "junta_directiva", "accionistas", "beneficiario_final",
    "referencias_comerciales", "referencias_bancarias", "informacion_bancaria_pagos", "clasificaciones",
    "tipos_transaccion",
]
_CAMPOS_JSON_LECTURA: List[str] = [
    "junta_directiva", "accionistas", "beneficiario_final",
    "referencias_comerciales", "referencias_bancarias", "informacion_bancaria_pagos", "clasificaciones",
    "tipos_transaccion",
]


def serializar_campos_json(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convierte listas y dicts a JSON strings para persistir en BD.

    Maneja tanto objetos Pydantic (con model_dump) como dicts planos.

    Args:
        datos: Diccionario con los campos del formulario a persistir.

    Returns:
        El mismo diccionario con los campos complejos convertidos a JSON string.
    """
    for campo in _CAMPOS_JSON_ESCRITURA:
        valor = datos.get(campo)
        if valor is None or not isinstance(valor, (list, dict)):
            continue
        elementos: List[Any] = valor if isinstance(valor, list) else [valor]
        serializados = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in elementos
        ]
        datos[campo] = json.dumps(serializados, ensure_ascii=False)
    return datos


def documentos_a_respuesta(documentos: List[Any]) -> List[Any]:
    """Convierte documentos ORM a lista de DocumentoResponse, excluyendo eliminados."""
    return [
        DocumentoResponse(
            id=d.id,
            tipo_documento=d.tipo_documento,
            nombre_archivo=d.nombre_archivo,
            content_type=d.content_type,
            tamano=d.tamano,
            created_at=d.created_at,
        )
        for d in documentos if d.deleted_at is None
    ]


def validaciones_a_dict(validaciones: List[Any]) -> List[Dict[str, Any]]:
    """Convierte validaciones ORM a lista de dicts para la respuesta."""
    return [
        {
            "id":               v.id,
            "tipo":             v.tipo,
            "campo":            v.campo,
            "resultado":        v.resultado,
            "detalle":          v.detalle,
            "valor_formulario": v.valor_formulario,
            "valor_documento":  v.valor_documento,
            "created_at":       v.created_at,
        }
        for v in validaciones
    ]


def construir_snapshot_formulario(formulario: Formulario) -> Dict[str, Any]:
    """Deserializa el formulario ORM y adjunta documentos y validaciones listos para respuesta."""
    datos = deserializar_campos_json(formulario)
    datos["documentos"] = documentos_a_respuesta(formulario.documentos)
    datos["validaciones"] = validaciones_a_dict(formulario.validaciones)
    return datos


def deserializar_campos_json(formulario: Formulario) -> Dict[str, Any]:
    """
    Convierte los JSON strings de la BD a sus tipos Python originales.

    Args:
        formulario: Instancia ORM del formulario.

    Returns:
        Diccionario con todos los campos, con los complejos ya deserializados.
    """
    datos: Dict[str, Any] = {
        columna.name: getattr(formulario, columna.name)
        for columna in formulario.__table__.columns
    }
    for campo in _CAMPOS_JSON_LECTURA:
        valor = datos.get(campo)
        if valor is None:
            continue
        try:
            datos[campo] = json.loads(valor)
        except (json.JSONDecodeError, TypeError):
            pass
    return datos
