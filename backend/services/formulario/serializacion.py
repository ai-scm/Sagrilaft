"""
Utilidades de serialización/deserialización y construcción de snapshots.

Trabaja exclusivamente con FormularioDatos (dominio) — el path ORM legacy
fue eliminado tras la migración de AccesoManualService a entidades de dominio.
"""

import dataclasses
from typing import Any, Dict, List

from domain.catalogo_correcciones import CAMPOS_CORREGIBLES
from domain.contratos import DocumentoDatos
from domain.formulario.entidades import FormularioDatos


# Campos de FormularioDatos que no son escalares del formulario.
_CAMPOS_EXCLUIDOS_DICT = frozenset({"documentos", "validaciones"})

# Fuente única de verdad para los campos versionables que se guardan junto al PDF.
_CAMPOS_VERSIONABLES_SNAPSHOT = CAMPOS_CORREGIBLES


def formulario_a_dict(formulario: FormularioDatos) -> Dict[str, Any]:
    """Convierte FormularioDatos a dict con todos sus campos escalares."""
    return {
        f.name: getattr(formulario, f.name)
        for f in dataclasses.fields(formulario)
        if f.name not in _CAMPOS_EXCLUIDOS_DICT
    }


def snapshot_version_formulario(formulario: FormularioDatos) -> Dict[str, Any]:
    """Campos del formulario que representan contenido versionable del PDF."""
    return {
        f.name: getattr(formulario, f.name)
        for f in dataclasses.fields(formulario)
        if f.name in _CAMPOS_VERSIONABLES_SNAPSHOT
    }


def documentos_a_respuesta(documentos: List[DocumentoDatos]) -> List[DocumentoDatos]:
    """Filtra documentos eliminados. La capa HTTP convierte a DocumentoResponse."""
    return [d for d in documentos if d.deleted_at is None]


def validaciones_a_dict(validaciones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Devuelve las validaciones ya como lista de dicts (FormularioDatos las almacena así)."""
    return validaciones or []


def construir_snapshot_formulario(formulario: FormularioDatos) -> Dict[str, Any]:
    """
    Construye el snapshot completo del formulario para la respuesta API.
    """
    datos = formulario_a_dict(formulario)
    datos["documentos"] = documentos_a_respuesta(formulario.documentos)
    datos["validaciones"] = validaciones_a_dict(formulario.validaciones)
    return datos
