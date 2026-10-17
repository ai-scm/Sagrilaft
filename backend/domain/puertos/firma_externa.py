"""
Puerto para servicios externos de firma electrónica.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable

from domain.contratos.firma import SolicitudFirmaCreada


@runtime_checkable
class IServicioFirmaExterna(Protocol):
    """
    Puerto para servicios externos de firma electrónica (ZohoSign, DocuSign, etc.).

    DIP: FirmaService depende de esta abstracción, no de ZohoSignService concreto.
    OCP: cambiar de proveedor solo requiere implementar este Protocol.
    """

    def crear_solicitud_firma_multiple(
        self,
        pdf_paths: List[Any],
        nombre_documento: str,
        correo_firmante: str,
        nombre_firmante: str,
    ) -> SolicitudFirmaCreada:
        """Envía uno o más PDFs al proveedor y crea la solicitud de firma."""
        ...

    def descargar_documento_firmado(self, request_id: str, destino: Any) -> Any:
        """Descarga el documento firmado a la ruta de destino y devuelve la ruta real."""
        ...

    def cancelar_solicitud_firma(self, request_id: str, motivo: Optional[str] = None) -> None:
        """Cancela una solicitud de firma activa."""
        ...

    def obtener_estado_solicitud(self, request_id: str) -> str:
        """Consulta el estado actual de una solicitud en el proveedor externo."""
        ...
