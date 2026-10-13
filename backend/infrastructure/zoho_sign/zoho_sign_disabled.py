"""Adaptador fail-closed para laboratorios P20 sin integración con Zoho Sign."""

from typing import Any, NoReturn

from domain.contratos import SolicitudFirmaCreada
from domain.excepciones import ZohoSignDeshabilitadoError


class ZohoSignDisabledService:
    """Nunca realiza llamadas de red ni simula una firma exitosa."""

    @staticmethod
    def _rechazar() -> NoReturn:
        raise ZohoSignDeshabilitadoError()

    def crear_solicitud_firma_multiple(
        self,
        pdf_paths: list[Any],
        nombre_documento: str,
        correo_firmante: str,
        nombre_firmante: str,
    ) -> SolicitudFirmaCreada:
        self._rechazar()

    def descargar_documento_firmado(self, request_id: str, destino: Any) -> Any:
        self._rechazar()

    def cancelar_solicitud_firma(self, request_id: str, motivo: str | None = None) -> None:
        self._rechazar()

    def obtener_estado_solicitud(self, request_id: str) -> str:
        self._rechazar()
