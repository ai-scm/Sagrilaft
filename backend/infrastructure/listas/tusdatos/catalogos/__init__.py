"""Catálogos oficiales de Tusdatos (ver README.md): nombres de fuentes y descripciones de hallazgos por código."""
import json
from functools import cache
from pathlib import Path

_DIRECTORIO = Path(__file__).resolve().parent


@cache
def _catalogo(nombre: str) -> dict[str, str]:
    datos = json.loads((_DIRECTORIO / f"{nombre}.json").read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in datos.items() if isinstance(v, str) and v.strip()}


def nombre_fuente(codigo: str) -> str | None:
    """Nombre oficial de la fuente según Tusdatos, o None si no está en el catálogo."""
    return _catalogo("fuentes").get(codigo)


def descripcion_hallazgo(codigo: str) -> str | None:
    """Descripción oficial del código de hallazgo (estable: Tusdatos pide usar el código, no el texto)."""
    return _catalogo("hallazgos").get(codigo)
