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
from pathlib import Path

from domain.constantes import (
    TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
)
from domain.contratos import DocumentoDatos, IServicioFirmaExterna
from domain.excepciones import (
    DocumentoNoEncontradoError,
    FirmaNoDisponibleError,
    FormularioNoEditableError,
    FormularioNoEncontradoError,
    WebhookTokenInvalidoError,
)
from domain.formulario.entidades import FormularioDatos
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.repositorios import RepositorioFirma
from services.firma.almacenamiento_firma import (
    archivar_version_anterior,
    resolver_ruta_certificado,
    resolver_ruta_documento_firmado,
)
from services.firma.certificado_pdf import generar_certificado_pdf

logger = logging.getLogger(__name__)

class FirmaService:
    """
    Orquesta el flujo de firma electrónica entre el portal y ZohoSign.

    Requiere que el formulario tenga un AccesoManual asociado para obtener
    el correo del firmante.
    """

    def __init__(
        self,
        repo: RepositorioFirma,
        zoho: IServicioFirmaExterna,
        upload_dir: Path,
        webhook_secret: str,
    ) -> None:
        self._repo           = repo
        self._zoho           = zoho
        self._upload_dir     = upload_dir
        self._webhook_secret = webhook_secret

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _obtener_formulario(self, formulario_id: str) -> FormularioDatos:
        formulario = self._repo.obtener_formulario(formulario_id)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _obtener_pdf_del_formulario(self, formulario_id: str) -> DocumentoDatos:
        doc = self._repo.obtener_pdf(formulario_id)
        if not doc:
            raise DocumentoNoEncontradoError(formulario_id, TIPO_DOCUMENTO_FORMULARIO_PDF)
        return doc

    def _registrar_certificado(self, formulario: FormularioDatos, ruta_certificado: Path) -> None:
        """
        Registra el certificado SAGRILAFT en documentos_adjuntos para trazabilidad.

        Si ya existe un registro previo (re-envío tras cancelación de firma), actualiza
        la ruta en lugar de crear un duplicado.
        """
        existente = self._repo.obtener_certificado(formulario.id)
        if existente:
            self._repo.actualizar_ruta_certificado(existente.id, str(ruta_certificado))
        else:
            self._repo.crear_documento({
                "formulario_id":  formulario.id,
                "tipo_documento": TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                "nombre_archivo": ruta_certificado.name,
                "ruta_archivo":   str(ruta_certificado),
            })

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

        acceso = self._repo.obtener_acceso_manual(formulario_id)
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

        ruta_certificado = resolver_ruta_certificado(pdf_path)
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

        # ZohoSign ya recibió el archivo; eliminarlo del disco evita que quede
        # el certificado sin firmar junto al paquete firmado final.
        if ruta_certificado.exists():
            ruta_certificado.unlink()
            logger.debug("Certificado temporal eliminado del disco: %s", ruta_certificado)

        self._repo.actualizar_formulario(formulario_id, {
            "zoho_request_id": resultado.request_id,
            "estado":          EstadoFormulario.PENDIENTE_FIRMA.value,
        })

        logger.info(
            "Formulario %s enviado a firma (paquete: formulario + certificado). "
            "ZohoSign request_id=%s → %s",
            formulario_id, resultado.request_id, acceso.correo_destinatario,
        )
        return {
            "request_id":      resultado.request_id,
            "estado":          EstadoFormulario.PENDIENTE_FIRMA.value,
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

        formulario = self._repo.obtener_formulario_por_zoho_id(request_id)

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

    def _procesar_firma_completada(self, formulario: FormularioDatos, request_id: str) -> str:
        if formulario.estado == EstadoFormulario.FIRMADO:
            logger.info("Webhook duplicado ignorado: formulario %s ya está FIRMADO", formulario.id)
            return EstadoFormulario.FIRMADO.value

        es_refirma_tras_correccion = formulario.ruta_documento_firmado is not None
        if es_refirma_tras_correccion:
            archivar_version_anterior(Path(formulario.ruta_documento_firmado))

        ruta_destino = resolver_ruta_documento_firmado(formulario, self._upload_dir)

        # descargar_documento_firmado puede ajustar la extensión a .zip si ZohoSign
        # devuelve múltiples documentos comprimidos. Usamos la ruta real retornada.
        ruta_guardada = self._zoho.descargar_documento_firmado(request_id, ruta_destino)

        self._repo.actualizar_formulario(formulario.id, {
            "ruta_documento_firmado": str(ruta_guardada),
            "estado":                 EstadoFormulario.FIRMADO.value,
        })

        logger.info("Formulario %s → FIRMADO. Archivo en: %s", formulario.id, ruta_guardada)
        return EstadoFormulario.FIRMADO.value

    def _procesar_firma_cancelada(
        self, formulario: FormularioDatos, request_id: str, status: str
    ) -> str:
        self._repo.actualizar_formulario(formulario.id, {
            "estado":          EstadoFormulario.VALIDADO.value,
            "zoho_request_id": None,
        })

        logger.info(
            "Formulario %s devuelto a VALIDADO (ZohoSign status='%s', request_id=%s)",
            formulario.id,
            status,
            request_id,
        )
        return EstadoFormulario.VALIDADO.value

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

        self._repo.actualizar_formulario(formulario_id, {
            "estado":          EstadoFormulario.VALIDADO.value,
            "zoho_request_id": None,
        })

        logger.info("Firma cancelada para formulario %s → VALIDADO", formulario_id)
        return {"estado": EstadoFormulario.VALIDADO.value}

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
        estado_nuevo = formulario.estado

        if estado_zoho.lower() == "completed":
            estado_nuevo = self._procesar_firma_completada(formulario, formulario.zoho_request_id)
        elif estado_zoho.lower() in ("declined", "expired", "recalled"):
            estado_nuevo = self._procesar_firma_cancelada(formulario, formulario.zoho_request_id, estado_zoho)

        logger.info(
            "Verificación manual formulario %s: ZohoSign='%s' → estado='%s'",
            formulario_id, estado_zoho, estado_nuevo,
        )
        return {"estado_zoho": estado_zoho, "estado": estado_nuevo}

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
