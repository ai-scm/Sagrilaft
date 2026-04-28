"""
Compatibilidad histórica.

Antes: los schemas HTTP vivían en `backend/schemas.py`.
Ahora: están organizados por contexto en `backend/api/schemas/`.

Mantén este módulo mientras migras imports antiguos:
  - Nuevo: `from api.schemas import FormularioResponse`
  - Antiguo: `from schemas import FormularioResponse`
"""

from api.schemas import *  # noqa: F403

