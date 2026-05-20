"""
FirmaService — lógica de negocio para el flujo de firma electrónica vía ZohoSign.

Responsabilidades:
  - Iniciar el proceso de firma de un formulario validado (VALIDADO → PENDIENTE_FIRMA).
  - Procesar los webhooks de ZohoSign y actualizar el estado del formulario.
  - Resolver la ruta del documento firmado para descarga.

Flujo de estados:
  VALIDADO → [enviar_a_firma] → PENDIENTE_FIRMA → [webhook Completed] → FIRMADO
                                                 → [webhook Declined]  → VALIDADO
"""

import hmac
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from domain.constantes import (
    TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
)
from domain.excepciones import (
    DocumentoNoEncontradoError,
    FirmaNoDisponibleError,
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    WebhookTokenInvalidoError,
)
from infrastructure.persistencia.models import (
    AccesoManual,
    DocumentoAdjunto,
    EstadoFormulario,
    Formulario,
)
from services.firma.certificado_pdf import generar_certificado_pdf
from services.formulario.almacenamiento_contraparte import resolver_ruta_contraparte
from services.zoho_sign.zoho_sign_service import ZohoSignService

logger = logging.getLogger(__name__)

_NOMBRE_PDF_FIRMADO = "formulario_firmado.pdf"


class FirmaService:
    """
    Orquesta el flujo de firma electrónica entre el portal y ZohoSign.

    Requiere que el formulario tenga un AccesoManual asociado para obtener
    el correo del firmante.
    """

    def __init__(
        self,
        sesion: Session,
        zoho: ZohoSignService,
        upload_dir: Path,
        webhook_secret: str,
    ) -> None:
        self._sesion        = sesion
        self._zoho          = zoho
        self._upload_dir    = upload_dir
        self._webhook_secret = webhook_secret

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _obtener_formulario(self, formulario_id: str) -> Formulario:
        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _obtener_pdf_del_formulario(self, formulario_id: str) -> DocumentoAdjunto:
        doc = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        if not doc:
            raise DocumentoNoEncontradoError(formulario_id, TIPO_DOCUMENTO_FORMULARIO_PDF)
        return doc

    def _registrar_certificado(self, formulario: Formulario, ruta_certificado: Path) -> None:
        """
        Registra el certificado SAGRILAFT en documentos_adjuntos para trazabilidad.

        Si ya existe un registro previo (re-envío tras cancelación de firma), actualiza
        la ruta en lugar de crear un duplicado. El commit lo hace el llamador.
        """
        existente = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario.id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        if existente:
            existente.ruta_archivo = str(ruta_certificado)
        else:
            self._sesion.add(DocumentoAdjunto(
                formulario_id=formulario.id,
                tipo_documento=TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                nombre_archivo=ruta_certificado.name,
                ruta_archivo=str(ruta_certificado),
            ))

    def _ruta_documento_firmado(self, formulario: Formulario) -> Path:
        directorio_contraparte = resolver_ruta_contraparte(
            tipo_contraparte=formulario.tipo_contraparte or "",
            razon_social=formulario.razon_social or "",
            upload_dir=self._upload_dir,
        )
        return directorio_contraparte / _NOMBRE_PDF_FIRMADO

    def _archivar_version_anterior(self, ruta_version_actual: Path) -> None:
        """
        Renombra el documento firmado existente añadiendo un sello de fecha/hora
        antes de guardar una nueva versión corregida.

        Convención:  formulario_firmado_corregido_YYYYMMDD_HHMMSS.pdf
        Si el archivo no existe en disco (ruta obsoleta de una migración anterior)
        el archivado se omite sin error.
        """
        if not ruta_version_actual.exists():
            logger.warning(
                "Archivo previo no encontrado en disco, se omite el archivado: %s",
                ruta_version_actual,
            )
            return

        sello_temporal = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        nombre_archivado = f"formulario_firmado_corregido_{sello_temporal}.pdf"
        ruta_archivada = ruta_version_actual.parent / nombre_archivado
        ruta_version_actual.rename(ruta_archivada)

        logger.info(
            "Versión anterior archivada: %s → %s",
            ruta_version_actual.name,
            ruta_archivada.name,
        )

    # ─── Enviar a firma ───────────────────────────────────────────────────────

    def enviar_a_firma(self, formulario_id: str) -> dict:
        """
        Inicia el proceso de firma electrónica para un formulario validado.

        1. Verifica que el formulario esté en estado VALIDADO.
        2. Obtiene el correo del firmante desde el AccesoManual asociado.
        3. Genera el Certificado de Terceros SAGRILAFT con los datos del formulario.
        4. Envía el formulario PDF + el certificado como paquete a ZohoSign.
        5. Actualiza el estado a PENDIENTE_FIRMA y guarda el zoho_request_id.

        Returns:
            {"request_id": str, "estado": str, "correo_firmante": str}
        """
        formulario = self._obtener_formulario(formulario_id)

        if formulario.estado != EstadoFormulario.VALIDADO:
            raise FormularioNoEditableError(
                f"El formulario debe estar en estado 'validado' para enviarse a firma "
                f"(estado actual: '{formulario.estado}')."
            )

        acceso = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )
        if not acceso:
            raise FormularioNoEditableError(
                "No se encontró un acceso manual asociado al formulario. "
                "No es posible obtener el correo del firmante."
            )

        pdf_doc  = self._obtener_pdf_del_formulario(formulario_id)
        pdf_path = Path(pdf_doc.ruta_archivo)
        if not pdf_path.exists():
            raise FormularioNoEditableError(
                f"El archivo PDF del formulario no existe en disco: {pdf_path}"
            )

        ruta_certificado = pdf_path.parent / "certificado_sagrilaft.pdf"
        generar_certificado_pdf(formulario, ruta_certificado)
        self._registrar_certificado(formulario, ruta_certificado)

        nombre_firmante  = formulario.nombre_representante or acceso.razon_social
        nombre_documento = f"SAGRILAFT — {acceso.razon_social}"

        # El formulario va primero; el certificado segundo. ZohoSign presenta
        # los documentos en ese orden al firmante durante la sesión de firma.
        resultado = self._zoho.crear_solicitud_firma_multiple(
            pdf_paths=[pdf_path, ruta_certificado],
            nombre_documento=nombre_documento,
            correo_firmante=acceso.correo_destinatario,
            nombre_firmante=nombre_firmante,
        )

        formulario.zoho_request_id = resultado.request_id
        formulario.estado          = EstadoFormulario.PENDIENTE_FIRMA
        self._sesion.commit()

        logger.info(
            "Formulario %s enviado a firma (paquete: formulario + certificado). "
            "ZohoSign request_id=%s → %s",
            formulario_id, resultado.request_id, acceso.correo_destinatario,
        )
        return {
            "request_id":      resultado.request_id,
            "estado":          formulario.estado,
            "correo_firmante": acceso.correo_destinatario,
        }

    # ─── Webhook ──────────────────────────────────────────────────────────────

    def procesar_webhook(
        self,
        *,
        secret_token: str,
        request_id: str,
        request_status: str,
    ) -> None:
        """
        Procesa una notificación de ZohoSign.

        Valida el secret_token y actualiza el estado del formulario según
        el resultado de la firma (Completed → FIRMADO, Declined/Expired → VALIDADO).

        Los parámetros llegan ya extraídos del payload HTTP (ver webhooks.py).
        """
        if not self._webhook_secret:
            raise RuntimeError("ZOHO_WEBHOOK_SECRET no está configurado en el servidor.")

        # Comparación en tiempo constante para evitar timing attacks
        if not hmac.compare_digest(secret_token, self._webhook_secret):
            logger.warning("Webhook ZohoSign rechazado: secret_token inválido")
            raise WebhookTokenInvalidoError()

        if not request_id:
            logger.warning("Webhook ZohoSign sin request_id — ignorado")
            return

        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.zoho_request_id == request_id)
            .first()
        )

        if not formulario:
            logger.info("Webhook ZohoSign: request_id=%s no corresponde a ningún formulario", request_id)
            return

        if request_status == "Completed":
            self._procesar_firma_completada(formulario, request_id)
        elif request_status in ("Declined", "Expired"):
            self._procesar_firma_cancelada(formulario, request_id, request_status)
        else:
            logger.info(
                "Webhook ZohoSign: formulario=%s status='%s' — no requiere acción",
                formulario.id,
                request_status,
            )

    def _procesar_firma_completada(self, formulario: Formulario, request_id: str) -> None:
        if formulario.estado == EstadoFormulario.FIRMADO:
            logger.info("Webhook duplicado ignorado: formulario %s ya está FIRMADO", formulario.id)
            return

        es_refirma_tras_correccion = formulario.ruta_documento_firmado is not None
        if es_refirma_tras_correccion:
            self._archivar_version_anterior(Path(formulario.ruta_documento_firmado))

        ruta_destino = self._ruta_documento_firmado(formulario)

        # descargar_documento_firmado puede ajustar la extensión a .zip si ZohoSign
        # devuelve múltiples documentos comprimidos. Usamos la ruta real retornada.
        ruta_guardada = self._zoho.descargar_documento_firmado(request_id, ruta_destino)

        formulario.ruta_documento_firmado = str(ruta_guardada)
        formulario.estado                 = EstadoFormulario.FIRMADO
        self._sesion.commit()

        logger.info("Formulario %s → FIRMADO. Archivo en: %s", formulario.id, ruta_guardada)

    def _procesar_firma_cancelada(
        self, formulario: Formulario, request_id: str, status: str
    ) -> None:
        formulario.estado          = EstadoFormulario.VALIDADO
        formulario.zoho_request_id = None
        self._sesion.commit()

        logger.info(
            "Formulario %s devuelto a VALIDADO (ZohoSign status='%s', request_id=%s)",
            formulario.id,
            status,
            request_id,
        )

    # ─── Cancelación de firma ────────────────────────────────────────────────

    def cancelar_firma(self, formulario_id: str) -> dict:
        """
        Cancela la solicitud de firma pendiente en ZohoSign y devuelve el formulario
        al estado VALIDADO para que pueda reenviarse a firma si es necesario.

        Solo es posible cuando el formulario está en estado PENDIENTE_FIRMA.
        """
        formulario = self._obtener_formulario(formulario_id)

        if formulario.estado != EstadoFormulario.PENDIENTE_FIRMA:
            raise FormularioNoEditableError(
                f"Solo se puede cancelar la firma cuando el formulario está en estado "
                f"'pendiente_firma' (estado actual: '{formulario.estado}')."
            )

        if not formulario.zoho_request_id:
            raise FormularioNoEditableError(
                "El formulario no tiene una solicitud de firma activa en ZohoSign."
            )

        self._zoho.cancelar_solicitud_firma(formulario.zoho_request_id)

        formulario.estado          = EstadoFormulario.VALIDADO
        formulario.zoho_request_id = None
        self._sesion.commit()

        logger.info("Firma cancelada para formulario %s → VALIDADO", formulario_id)
        return {"estado": formulario.estado}

    # ─── Verificación manual de estado ───────────────────────────────────────

    def verificar_estado_firma(self, formulario_id: str) -> dict:
        """
        Consulta ZohoSign y aplica la transición de estado si la firma cambió.
        Equivalente al webhook pero activado manualmente desde el portal.
        """
        formulario = self._obtener_formulario(formulario_id)

        if formulario.estado != EstadoFormulario.PENDIENTE_FIRMA:
            raise FormularioNoEditableError(
                f"Solo se puede verificar en estado 'pendiente_firma' (actual: '{formulario.estado}')."
            )

        if not formulario.zoho_request_id:
            raise FormularioNoEditableError("No hay solicitud de firma activa.")

        estado_zoho = self._zoho.obtener_estado_solicitud(formulario.zoho_request_id)

        if estado_zoho.lower() == "completed":
            self._procesar_firma_completada(formulario, formulario.zoho_request_id)
        elif estado_zoho.lower() in ("declined", "expired", "recalled"):
            self._procesar_firma_cancelada(formulario, formulario.zoho_request_id, estado_zoho)

        logger.info(
            "Verificación manual formulario %s: ZohoSign='%s' → estado='%s'",
            formulario_id, estado_zoho, formulario.estado,
        )
        return {"estado_zoho": estado_zoho, "estado": formulario.estado}

    # ─── Descarga del firmado ─────────────────────────────────────────────────

    def resolver_documento_firmado(self, formulario_id: str) -> Path:
        """
        Devuelve la ruta en disco del PDF firmado.

        Lanza FirmaNoDisponibleError si el formulario no está en estado FIRMADO
        o si el archivo no existe en disco.
        """
        formulario = self._obtener_formulario(formulario_id)

        if formulario.estado != EstadoFormulario.FIRMADO or not formulario.ruta_documento_firmado:
            raise FirmaNoDisponibleError(formulario_id)

        ruta = Path(formulario.ruta_documento_firmado)
        if not ruta.exists():
            raise FirmaNoDisponibleError(formulario_id)

        return ruta
