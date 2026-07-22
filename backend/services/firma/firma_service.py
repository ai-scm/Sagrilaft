"""
FirmaService — lógica de negocio para el flujo de firma electrónica vía ZohoSign.

Flujo de estados:
  VALIDADO → [enviar_a_firma] → PENDIENTE_FIRMA → [webhook Completed] → FIRMADO
                                                 → [webhook Declined]  → VALIDADO
  FIRMADO → [reabrir revisión interna] → ENVIADO
"""

import hashlib
import hmac
import logging
import tempfile
from pathlib import Path
from typing import Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
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
from domain.formulario.entidades import FormularioDatos, FormularioDominio
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.repositorios import RepositorioFirma
from services.firma.almacenamiento_firma import (
    resolver_key_documento_firmado,
    resolver_ruta_certificado,
)
from services.firma.certificado_pdf import generar_certificado_pdf

logger = logging.getLogger(__name__)


class FirmaService:
    """Orquesta el flujo de firma electrónica entre el portal y ZohoSign."""

    def __init__(
        self,
        repo: RepositorioFirma,
        zoho: IServicioFirmaExterna,
        storage: IAlmacenamiento,
        webhook_secret: str,
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        alertas_portal: Optional[IAlertasPortal] = None,
    ) -> None:
        self._repo           = repo
        self._zoho           = zoho
        self._storage        = storage
        self._webhook_secret = webhook_secret
        self._auditoria      = repo_auditoria
        self._alertas        = alertas_portal

    def _registrar(self, evento: EventoAuditoria) -> None:
        if self._auditoria:
            self._auditoria.registrar_evento(evento)

    def _alertar(self, tipo: TipoAlerta, formulario: FormularioDatos, detalle: Optional[str] = None) -> None:
        """Dispara una alerta al portal si el adaptador está disponible."""
        if self._alertas:
            self._alertas.alertar(
                tipo=tipo,
                formulario_id=formulario.id,
                razon_social=formulario.razon_social or "",
                tipo_contraparte=formulario.tipo_contraparte or "",
                codigo_peticion=formulario.codigo_peticion,
                detalle=detalle,
            )

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _obtener_formulario(self, formulario_id: str, bloquear: bool = False) -> FormularioDatos:
        formulario = self._repo.obtener_formulario(formulario_id, bloquear=bloquear)
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
        El certificado es temporal (se envía a Zoho y se elimina) — la ruta en BD
        es solo un registro de auditoría.
        """
        existente = self._repo.obtener_certificado(formulario.id)
        hash_calc = hashlib.sha256(ruta_certificado.read_bytes()).hexdigest()
        tamano_calc = ruta_certificado.stat().st_size
        if existente:
            self._repo.actualizar_certificado(
                existente.id,
                str(ruta_certificado),
                tamano_calc,
                hash_calc,
            )
        else:
            self._repo.crear_documento({
                "formulario_id":  formulario.id,
                "tipo_documento": TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                "nombre_archivo": ruta_certificado.name,
                "ruta_archivo":   str(ruta_certificado),
                "tamano":         tamano_calc,
                "subido_por":     ActorTipo.SISTEMA,
                "hash_sha256":    hash_calc,
            })

    # ─── Enviar a firma ───────────────────────────────────────────────────────

    def enviar_a_firma(self, formulario_id: str, actor_id: Optional[str] = None) -> dict:
        """
        Inicia el proceso de firma electrónica para un formulario validado.

        1. Verifica que el formulario esté en estado VALIDADO.
        2. Descarga el PDF desde el backend de almacenamiento a un archivo local temporal.
        3. Genera el Certificado de Terceros SAGRILAFT.
        4. Envía ambos PDFs a ZohoSign.
        5. Actualiza el estado a PENDIENTE_FIRMA.
        """
        formulario = self._obtener_formulario(formulario_id, bloquear=True)
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.iniciar_firma()  # VALIDADO → PENDIENTE_FIRMA; lanza FormularioNoEditableError si no aplica

        acceso = self._repo.obtener_acceso_manual(formulario_id)
        if not acceso:
            raise FormularioNoEditableError(
                "No se encontró un acceso manual asociado al formulario. "
                "No es posible obtener el correo del firmante."
            )

        pdf_doc = self._obtener_pdf_del_formulario(formulario_id)

        if not self._storage.existe(pdf_doc.ruta_archivo):
            raise FormularioNoEditableError(
                f"El PDF del formulario no existe en el backend de almacenamiento: {pdf_doc.ruta_archivo}"
            )

        with self._storage.como_archivo_local(pdf_doc.ruta_archivo, pdf_doc.nombre_archivo) as pdf_path:
            ruta_certificado = resolver_ruta_certificado(pdf_path)
            try:
                generar_certificado_pdf(formulario, ruta_certificado)
                self._registrar_certificado(formulario, ruta_certificado)

                nombre_firmante  = formulario.nombre_representante or acceso.razon_social
                nombre_documento = f"SAGRILAFT — {acceso.razon_social}"

                if not acceso.correo_destinatario:
                    raise FormularioNoEditableError(
                        "El destinatario aún no ha confirmado su correo electrónico. "
                        "No es posible iniciar la firma hasta que complete ese paso."
                    )

                resultado = self._zoho.crear_solicitud_firma_multiple(
                    pdf_paths=[pdf_path, ruta_certificado],
                    nombre_documento=nombre_documento,
                    correo_firmante=acceso.correo_destinatario,
                    nombre_firmante=nombre_firmante,
                )
            finally:
                if ruta_certificado.exists():
                    ruta_certificado.unlink()
                    logger.debug("Certificado temporal eliminado: %s", ruta_certificado)

        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FIRMA_INICIADA,
            estado_anterior=formulario.estado,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
        ))
        self._repo.actualizar_formulario(formulario_id, {
            "zoho_request_id": resultado.request_id,
            "estado":          dominio.estado.value,
        })
        self._alertar(TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA, formulario)

        logger.info(
            "Formulario %s enviado a firma. ZohoSign request_id=%s",
            formulario_id, resultado.request_id,
        )
        return {
            "request_id":      resultado.request_id,
            "estado":          dominio.estado.value,
            "correo_firmante": acceso.correo_destinatario,
        }

    # ─── Webhook ──────────────────────────────────────────────────────────────

    def procesar_webhook(self, *, secret_token: str, request_id: str, request_status: str) -> None:
        """Compatibilidad con webhooks que envian secret_token en el payload."""
        if not self._webhook_secret:
            raise RuntimeError("ZOHO_WEBHOOK_SECRET no está configurado en el servidor.")

        if not hmac.compare_digest(secret_token, self._webhook_secret):
            logger.warning("Webhook ZohoSign rechazado: secret_token inválido")
            raise WebhookTokenInvalidoError()

        self.procesar_webhook_verificado(request_id=request_id, request_status=request_status)

    def procesar_webhook_verificado(self, *, request_id: str, request_status: str) -> None:
        if not request_id:
            logger.warning("Webhook ZohoSign sin request_id — ignorado")
            return

        formulario = self._repo.obtener_formulario_por_zoho_id(request_id, bloquear=True)
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
                formulario.id, request_status,
            )

    def _procesar_firma_completada(self, formulario: FormularioDatos, request_id: str) -> str:
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.completar_firma()  # PENDIENTE_FIRMA → FIRMADO; no-op idempotente si ya es FIRMADO

        if formulario.estado == EstadoFormulario.FIRMADO:
            logger.info("Webhook duplicado ignorado: formulario %s ya está FIRMADO", formulario.id)
            return dominio.estado.value

        key_destino = resolver_key_documento_firmado(formulario, request_id)

        # ZohoSign descarga a un archivo local temporal; luego lo subimos al backend.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_ruta = Path(tmp_dir) / Path(key_destino).name
            ruta_local = self._zoho.descargar_documento_firmado(request_id, tmp_ruta)
            # ZohoSign puede devolver .zip si hay múltiples documentos
            key_guardado = str(Path(key_destino).with_suffix(ruta_local.suffix))
            self._storage.guardar_desde_archivo_local(key_guardado, ruta_local)

        self._registrar(EventoAuditoria(
            formulario_id=formulario.id,
            tipo_evento=TipoEvento.FIRMA_COMPLETADA,
            estado_anterior=formulario.estado,
            estado_nuevo=dominio.estado.value,
            actor_id=request_id,
            actor_tipo=ActorTipo.SISTEMA,
        ))
        self._repo.actualizar_formulario(formulario.id, {
            "ruta_documento_firmado": key_guardado,
            "estado":                 dominio.estado.value,
        })
        self._alertar(TipoAlerta.FORMULARIO_FIRMADO, formulario)

        logger.info("Formulario %s → FIRMADO. Key: %s", formulario.id, key_guardado)
        return dominio.estado.value

    def _procesar_firma_cancelada(self, formulario: FormularioDatos, request_id: str, status: str) -> str:
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.cancelar_firma()  # PENDIENTE_FIRMA → VALIDADO; lanza FormularioNoEditableError si no aplica
        self._registrar(EventoAuditoria(
            formulario_id=formulario.id,
            tipo_evento=TipoEvento.FIRMA_CANCELADA,
            estado_anterior=formulario.estado,
            estado_nuevo=dominio.estado.value,
            actor_id=request_id,
            actor_tipo=ActorTipo.SISTEMA,
        ))
        self._repo.actualizar_formulario(formulario.id, {
            "estado":          dominio.estado.value,
            "zoho_request_id": None,
        })
        logger.info(
            "Formulario %s devuelto a VALIDADO (ZohoSign status='%s', request_id=%s)",
            formulario.id, status, request_id,
        )
        return dominio.estado.value

    # ─── Cancelación de firma ────────────────────────────────────────────────

    def cancelar_firma(self, formulario_id: str, actor_id: Optional[str] = None) -> dict:
        formulario = self._obtener_formulario(formulario_id, bloquear=True)
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.cancelar_firma()  # PENDIENTE_FIRMA → VALIDADO; lanza FormularioNoEditableError si no aplica

        if not formulario.zoho_request_id:
            raise FormularioNoEditableError(
                "El formulario no tiene una solicitud de firma activa en ZohoSign."
            )

        self._zoho.cancelar_solicitud_firma(formulario.zoho_request_id)
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FIRMA_CANCELADA,
            estado_anterior=formulario.estado,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
        ))
        self._repo.actualizar_formulario(formulario_id, {
            "estado":          dominio.estado.value,
            "zoho_request_id": None,
        })

        logger.info("Firma cancelada para formulario %s → VALIDADO", formulario_id)
        return {"estado": dominio.estado.value}

    # ─── Verificación manual de estado ───────────────────────────────────────

    def verificar_estado_firma(self, formulario_id: str) -> dict:
        formulario = self._obtener_formulario(formulario_id, bloquear=True)

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

    def resolver_documento_firmado(self, formulario_id: str) -> InfoDescarga:
        """Genera la info de descarga del PDF firmado. El caller decide el tipo de respuesta según InfoDescarga.es_url."""
        formulario = self._obtener_formulario(formulario_id)

        if not formulario.ruta_documento_firmado:
            raise FirmaNoDisponibleError(formulario_id)

        key = formulario.ruta_documento_firmado
        if not self._storage.existe(key):
            raise FirmaNoDisponibleError(formulario_id)

        es_zip = key.endswith(".zip")
        nombre = "formulario_firmado.zip" if es_zip else "formulario_firmado.pdf"
        content_type = "application/zip" if es_zip else "application/pdf"

        return self._storage.info_descarga(key, nombre, content_type)
