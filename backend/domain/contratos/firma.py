"""
DTOs del resultado de creación de solicitudes de firma electrónica.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SolicitudFirmaCreada:
    """Resultado de crear una solicitud de firma electrónica en un proveedor externo."""
    request_id: str
