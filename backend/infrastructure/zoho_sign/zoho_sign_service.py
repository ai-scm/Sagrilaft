"""
ZohoSignService — cliente HTTP para la API de ZohoSign (datacenter US).

Responsabilidades:
  - Gestionar el ciclo de vida del access token (refresco automático con caché).
  - Crear solicitudes de firma enviando el PDF del formulario.
  - Descargar el PDF firmado una vez completada la firma.

Referencia API: https://www.zoho.com/sign/api/
"""

import contextlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from domain.contratos import SolicitudFirmaCreada
from infrastructure.configuracion import ZohoSignConfig

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
_API_BASE  = "https://sign.zoho.com/api/v1"

# Margen de 5 minutos antes de que el token expire para forzar refresco anticipado
_MARGEN_REFRESCO_SEGUNDOS = 300


class ZohoSignService:
    """Cliente síncrono para ZohoSign. Una instancia por request es segura."""

    def __init__(self, config: ZohoSignConfig) -> None:
        self._config = config
        self._access_token: str | None = None
        self._token_expiry: datetime = datetime.min.replace(tzinfo=timezone.utc)

    # ─── Token management ─────────────────────────────────────────────────────

    def _obtener_token(self) -> str:
        """Devuelve un access token válido, refrescándolo si está próximo a expirar."""
        if self._access_token and datetime.now(timezone.utc) < self._token_expiry:
            return self._access_token

        logger.info("Refrescando access token de ZohoSign")
        resp = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "client_id":     self._config.client_id,
                "client_secret": self._config.client_secret,
                "refresh_token": self._config.refresh_token,
                "redirect_uri":  self._config.redirect_uri,
            },
            timeout=15,
        )
        resp.raise_for_status()
        datos = resp.json()

        if "access_token" not in datos:
            raise RuntimeError(f"ZohoSign no devolvió access_token: {datos}")

        self._access_token = datos["access_token"]
        expires_in = int(datos.get("expires_in", 3600))
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - _MARGEN_REFRESCO_SEGUNDOS)
        return self._access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self._obtener_token()}"}

    # ─── Firma ────────────────────────────────────────────────────────────────

    def crear_solicitud_firma_multiple(
        self,
        pdf_paths: list[Path],
        nombre_documento: str,
        correo_firmante: str,
        nombre_firmante: str,
    ) -> SolicitudFirmaCreada:
        """
        Sube varios PDFs a ZohoSign como un paquete unificado y envía la solicitud
        de firma en dos pasos:

        1. POST /api/v1/requests — sube todos los PDFs y crea el borrador.
        2. POST /api/v1/requests/{id}/submit — dispara el correo al firmante.

        El firmante recibe un solo email y firma todos los documentos en una sesión.
        El orden de pdf_paths determina el orden visual en ZohoSign.

        ZohoSign detecta el tag {{S:R1*...}} embebido en cada PDF y posiciona
        el campo de firma automáticamente en cada documento.
        """
        if not pdf_paths:
            raise ValueError("Se requiere al menos un PDF.")

        for p in pdf_paths:
            if not p.exists():
                raise FileNotFoundError(f"PDF no encontrado: {p}")

        # modo_prueba=True → sandbox: llamadas reales a Zoho con testing=true
        #   → emails reales a la contraparte, firma real, sin consumo de créditos
        # modo_prueba=False → producción: llamadas reales sin testing param
        params = {"testing": "true"} if self._config.modo_prueba else {}

        data_crear = {
            "requests": {
                "request_name":    nombre_documento,
                "expiration_days": 5,
                "is_sequential":   True,
                "actions": [
                    {
                        "action_type":     "SIGN",
                        "recipient_email": correo_firmante,
                        "recipient_name":  nombre_firmante,
                        "signing_order":   0,
                    }
                ],
            }
        }

        logger.info(
            "Paso 1/2 ZohoSign (paquete %d docs) — '%s' → %s [sandbox=%s]",
            len(pdf_paths), nombre_documento, correo_firmante, self._config.modo_prueba,
        )

        # ExitStack garantiza el cierre de todos los archivos aunque falle alguno
        with contextlib.ExitStack() as stack:
            archivos = [
                ("file", (p.name, stack.enter_context(open(p, "rb")), "application/pdf"))
                for p in pdf_paths
            ]
            resp_crear = httpx.post(
                f"{_API_BASE}/requests",
                headers=self._headers(),
                params=params,
                data={"data": json.dumps(data_crear)},
                files=archivos,
                timeout=30,
            )

        if not resp_crear.is_success:
            raise RuntimeError(
                f"ZohoSign rechazó la creación del paquete (HTTP {resp_crear.status_code}): "
                f"{resp_crear.text[:500]}"
            )
        datos_crear = resp_crear.json()

        if datos_crear.get("code") != 0:
            raise RuntimeError(
                f"ZohoSign rechazó el paquete (code={datos_crear.get('code')}): "
                f"{datos_crear.get('message', 'sin detalle')}"
            )

        solicitud  = datos_crear["requests"]
        request_id = solicitud["request_id"]
        action_id  = solicitud["actions"][0]["action_id"]
        n_docs     = len(solicitud.get("document_ids", []))

        logger.info(
            "Borrador ZohoSign creado (paquete): request_id=%s action_id=%s documentos=%d",
            request_id, action_id, n_docs,
        )

        # ── Paso 2: submit ────────────────────────────────────────────────────
        data_enviar = {
            "requests": {
                "actions": [{"action_id": action_id, "action_type": "SIGN"}]
            }
        }

        logger.info("Paso 2/2 ZohoSign — enviando paquete a firma: request_id=%s", request_id)

        resp_enviar = httpx.post(
            f"{_API_BASE}/requests/{request_id}/submit",
            headers=self._headers(),
            params=params,
            data={"data": json.dumps(data_enviar)},
            timeout=30,
        )

        if not resp_enviar.is_success:
            raise RuntimeError(
                f"ZohoSign rechazó el submit del paquete (HTTP {resp_enviar.status_code}): "
                f"{resp_enviar.text[:500]}"
            )
        datos_enviar = resp_enviar.json()

        if datos_enviar.get("code", 0) != 0:
            raise RuntimeError(
                f"ZohoSign rechazó el envío del paquete (code={datos_enviar.get('code')}): "
                f"{datos_enviar.get('message', 'sin detalle')}"
            )

        logger.info(
            "Paquete ZohoSign enviado a firma: request_id=%s → %s",
            request_id, correo_firmante,
        )
        return SolicitudFirmaCreada(request_id=request_id)

    # ─── Cancelación ──────────────────────────────────────────────────────────

    def cancelar_solicitud_firma(self, request_id: str) -> None:
        """
        Cancela una solicitud de firma pendiente vía recall.

        POST /api/v1/requests/{id}/recall
        No requiere cuerpo. Después del recall los destinatarios ya no pueden firmar.
        """
        if self._config.modo_prueba:
            logger.info("ZohoSign sandbox: cancelando solicitud real request_id=%s", request_id)

        resp = httpx.post(
            f"{_API_BASE}/requests/{request_id}/recall",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        datos = resp.json()

        if datos.get("code") != 0:
            raise RuntimeError(
                f"ZohoSign rechazó el recall (code={datos.get('code')}): "
                f"{datos.get('message', 'sin detalle')}"
            )

        logger.info("Solicitud ZohoSign cancelada (recall): request_id=%s", request_id)

    # ─── Consulta de estado ───────────────────────────────────────────────────

    def obtener_estado_solicitud(self, request_id: str) -> str:
        """Devuelve el request_status actual de una solicitud en ZohoSign."""
        if self._config.modo_prueba:
            logger.info("ZohoSign sandbox: consultando estado real request_id=%s", request_id)

        resp = httpx.get(
            f"{_API_BASE}/requests/{request_id}",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        datos = resp.json()

        if datos.get("code") != 0:
            raise RuntimeError(
                f"ZohoSign error al consultar solicitud (code={datos.get('code')}): "
                f"{datos.get('message', 'sin detalle')}"
            )

        return (datos.get("requests") or {}).get("request_status", "")

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def descargar_documento_firmado(self, request_id: str, destino: Path) -> Path:
        """
        Descarga el documento firmado desde ZohoSign y lo guarda en `destino`.

        Endpoint: GET /api/v1/requests/{id}/pdf?merge=true&with_coc=true
          - merge=true   → consolida todos los documentos firmados en un solo archivo.
          - with_coc=true → incluye el certificado de completado (audit trail SAGRILAFT).

        Flujo:
          1. Verifica que ZohoSign reporta la solicitud como Completed.
          2. Descarga el archivo y valida el content-type.

        El archivo resultante puede ser:
          - application/pdf  → un solo documento firmado (caso normal).
          - application/zip  → múltiples documentos; destino se guarda como .zip.
        """
        logger.info("Descargando documento firmado: request_id=%s → %s", request_id, destino)

        estado_zoho = self.obtener_estado_solicitud(request_id)
        if estado_zoho.lower() != "completed":
            raise RuntimeError(
                f"ZohoSign: la solicitud '{request_id}' no está completada "
                f"(estado actual: '{estado_zoho}'). No se puede descargar el archivo."
            )

        # Descargar el documento firmado (con certificado de completado)
        resp_archivo = httpx.get(
            f"{_API_BASE}/requests/{request_id}/pdf",
            params={"merge": "true", "with_coc": "true"},
            headers=self._headers(),
            timeout=60,
            follow_redirects=True,
        )
        resp_archivo.raise_for_status()

        # Validar content-type: PDF (un doc) o ZIP (múltiples docs)
        content_type = resp_archivo.headers.get("content-type", "")
        _TIPOS_VALIDOS = ("application/pdf", "application/zip", "application/octet-stream")
        if not any(t in content_type for t in _TIPOS_VALIDOS):
            raise RuntimeError(
                f"ZohoSign devolvió content-type inesperado: '{content_type}'. "
                f"Respuesta: {resp_archivo.text[:300]}"
            )

        # Ajustar extensión si ZohoSign devuelve ZIP (múltiples documentos)
        ruta_final = destino
        if "zip" in content_type:
            ruta_final = destino.with_suffix(".zip")
            logger.info("Respuesta ZIP (múltiples documentos): guardando como %s", ruta_final)

        ruta_final.parent.mkdir(parents=True, exist_ok=True)
        ruta_final.write_bytes(resp_archivo.content)

        logger.info("Documento firmado guardado: %s (%d bytes)", ruta_final, len(resp_archivo.content))
        return ruta_final
