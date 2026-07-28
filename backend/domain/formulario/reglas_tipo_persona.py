"""Reglas de negocio asociadas al tipo de persona del formulario."""

from typing import Any, Dict

from domain.formulario.tipos import TipoPersona

_CAMPOS_PERSONA_NATURAL = [
    "direccion_residencia",
    "ciudad_residencia",
]

_CAMPOS_CLASIFICACION_TRIBUTARIA = [
    "actividad_clasificacion",
    "actividad_especifica",
    "sector",
    "superintendencia",
    "responsabilidades_renta",
    "autorretenedor",
    "responsabilidades_iva",
    "regimen_iva",
    "gran_contribuyente",
    "entidad_sin_animo_lucro",
    "retencion_ica",
    "impuesto_ica",
    "entidad_oficial",
    "exento_retencion_fuente",
]

_LISTAS_SOLO_JURIDICA = [
    "junta_directiva",
    "accionistas",
    "beneficiario_final",
]


def purgar_campos_no_aplicables(datos: Dict[str, Any], tipo_persona: str) -> Dict[str, Any]:
    """Elimina campos que no corresponden al tipo de persona."""
    resultado = dict(datos)
    tipo = tipo_persona.lower() if tipo_persona else ""

    if tipo == TipoPersona.NATURAL.value:
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA:
            resultado.pop(campo, None)
        for lista in _LISTAS_SOLO_JURIDICA:
            resultado[lista] = []
    elif tipo == TipoPersona.JURIDICA.value:
        for campo in _CAMPOS_PERSONA_NATURAL:
            resultado.pop(campo, None)

    return resultado
