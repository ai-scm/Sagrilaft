"""
Compatibilidad histórica.

Antes: estas utilidades vivían en `services.utils.fechas`.
Ahora: están en `core.fechas` para evitar que infraestructura dependa de services.
"""

from core.fechas import *  # noqa: F403
