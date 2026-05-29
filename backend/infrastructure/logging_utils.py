"""
Re-exporta sanitizar_log desde domain/utils/seguridad.py.

La función vive en el dominio porque es una regla de seguridad de negocio
(prevención de log injection en registros de auditoría SAGRILAFT).
Este módulo se mantiene para compatibilidad con imports existentes.
"""

from domain.utils.seguridad import sanitizar_log  # noqa: F401
