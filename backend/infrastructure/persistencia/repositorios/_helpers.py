"""
Funciones auxiliares genéricas de serialización, normalización y conversión.

Estas utilidades son compartidas por múltiples repositorios y mappers.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List


# Campos que se almacenan como JSON string en la base de datos.
# Deben serializarse al escribir y deserializarse al leer.
_CAMPOS_JSON = ["snapshot_datos"]

_CAMPOS_BOOLEANOS_SI_NO = {
    "realiza_operaciones_moneda_extranjera",
    "autorretenedor",
    "gran_contribuyente",
    "entidad_sin_animo_lucro",
    "retencion_ica",
    "impuesto_ica",
    "entidad_oficial",
    "exento_retencion_fuente",
}


def _fila_orm_a_dict(fila: Any, atributos: List[str]) -> Dict[str, Any]:
    """Convierte una fila ORM hija (ej. MiembroJuntaDirectiva) al dict plano que espera el dominio."""
    return {atributo: getattr(fila, atributo) for atributo in atributos}


def _deserializar_json(valor: Any) -> Any:
    """Convierte un JSON string almacenado en BD a su tipo Python (lista/dict)."""
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except (json.JSONDecodeError, TypeError):
            return valor
    return valor


def _serializar_json(valor: Any) -> Any:
    """Convierte listas/dicts Python a JSON string para almacenar en BD."""
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, default=_valor_json)
    return valor


def _valor_json(valor: Any) -> Any:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(f"Object of type {type(valor).__name__} is not JSON serializable")


def _aplicar_serializacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Serializa los campos JSON de un dict antes de persistirlo."""
    resultado = dict(datos)
    for campo in _CAMPOS_JSON:
        if campo in resultado:
            resultado[campo] = _serializar_json(resultado[campo])
    return resultado


def _normalizar_booleanos_no_nulos(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Evita NULL en columnas Boolean no nulas cuando un borrador envía campo vacío."""
    resultado = dict(datos)
    for campo in _CAMPOS_BOOLEANOS_SI_NO:
        if campo in resultado and resultado[campo] is None:
            resultado[campo] = False
    return resultado


def _normalizar_enum_str(valor: str | None) -> str:
    """Convierte 'EnumClass.MEMBER' → 'member'. Sin efecto sobre valores ya correctos."""
    if not valor:
        return ""
    if "." in valor:
        return valor.rsplit(".", 1)[1].lower()
    return valor
