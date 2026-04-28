"""
Utilidades de estado de formulario.

Centraliza la interpretación del campo `Formulario.estado` para evitar bugs por
mezcla de tipos (string vs enum) y mantener lenguaje ubicuo en el dominio.
"""

from typing import Any, Optional

from infrastructure.persistencia.models import EstadoFormulario


def normalizar_estado_formulario(estado: Any) -> Optional[str]:
    """Convierte un estado a su representación canónica (string) o None."""
    if estado is None:
        return None
    if isinstance(estado, EstadoFormulario):
        return estado.value
    return str(estado)


def es_estado_borrador(estado: Any) -> bool:
    """True si el estado representa 'borrador' (soporta enum o string)."""
    return normalizar_estado_formulario(estado) == EstadoFormulario.BORRADOR.value

