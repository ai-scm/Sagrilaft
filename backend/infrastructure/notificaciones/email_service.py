"""
EmailService — envío de correos transaccionales del sistema SAGRILAFT.

Es un no-op silencioso si SMTP no está configurado, para no bloquear flujos
de trabajo en entornos sin correo (desarrollo local, staging sin SMTP, etc.).
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.configuracion import SmtpConfig
from domain.catalogo_correcciones import resolver_etiquetas

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    def _smtp_configurado(self) -> bool:
        return bool(self._config.host and self._config.usuario)

    def enviar_notificacion_devolucion(
        self,
        correo_destinatario: str,
        especificaciones_correccion: str,
        enlace_diligenciamiento: str | None = None,
        campos_identificados: list[str] | None = None,
    ) -> bool:
        """
        Notifica al destinatario que debe corregir su formulario SAGRILAFT.

        Si se proporcionan campos_identificados, el correo los lista con sus
        etiquetas legibles para que la contraparte sepa exactamente qué corregir
        antes de abrir el formulario.

        Returns:
            True si el correo se envió correctamente; False si SMTP no está
            configurado o si ocurrió un error de envío (no lanza excepción).
        """
        if not self._smtp_configurado():
            logger.warning(
                "SMTP no configurado — se omite notificación de devolución a '%s'.",
                correo_destinatario,
            )
            return False

        asunto      = "Formulario SAGRILAFT — Requiere correcciones"
        cuerpo_texto = _construir_cuerpo_texto(
            especificaciones_correccion, enlace_diligenciamiento, campos_identificados,
        )
        cuerpo_html  = _construir_cuerpo_html(
            especificaciones_correccion, enlace_diligenciamiento, campos_identificados,
        )
        remitente    = self._config.remitente or self._config.usuario

        mensaje = _construir_mensaje(
            remitente=remitente,
            destinatario=correo_destinatario,
            asunto=asunto,
            cuerpo_texto=cuerpo_texto,
            cuerpo_html=cuerpo_html,
        )

        return self._enviar(mensaje, correo_destinatario)

    def _enviar(self, mensaje: MIMEMultipart, destinatario: str) -> bool:
        try:
            with smtplib.SMTP(self._config.host, self._config.puerto) as servidor:
                servidor.starttls()
                servidor.login(self._config.usuario, self._config.contrasena)
                servidor.sendmail(
                    from_addr=mensaje["From"],
                    to_addrs=[destinatario],
                    msg=mensaje.as_string(),
                )
            logger.info("Notificación de devolución enviada a '%s'.", destinatario)
            return True
        except Exception:
            logger.exception(
                "Error al enviar notificación de devolución a '%s'.", destinatario
            )
            return False


# ── Helpers de plantillas ─────────────────────────────────────────────────────

def _construir_mensaje(
    remitente: str,
    destinatario: str,
    asunto: str,
    cuerpo_texto: str,
    cuerpo_html: str,
) -> MIMEMultipart:
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = asunto
    mensaje["From"]    = remitente
    mensaje["To"]      = destinatario
    mensaje.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    mensaje.attach(MIMEText(cuerpo_html,  "html",  "utf-8"))
    return mensaje


def _construir_cuerpo_texto(
    especificaciones: str,
    enlace: str | None,
    campos_identificados: list[str] | None = None,
) -> str:
    seccion_campos = ""
    if campos_identificados:
        etiquetas = resolver_etiquetas(campos_identificados)
        lineas = "\n".join(f"  - {e}" for e in etiquetas)
        seccion_campos = f"\nCampos que requieren corrección:\n{lineas}\n"

    seccion_enlace = (
        f"\nAcceda aquí para realizar las correcciones:\n{enlace}\n"
        if enlace
        else "\nPor favor acceda al portal para realizar las correcciones solicitadas.\n"
    )
    return (
        "Estimado usuario,\n\n"
        "Usted ha sido requerido para completar/modificar la siguiente información "
        "del formulario:\n\n"
        f"{especificaciones}\n"
        f"{seccion_campos}"
        f"{seccion_enlace}\n"
        "Equipo Blend360"
    )


def _construir_cuerpo_html(
    especificaciones: str,
    enlace: str | None,
    campos_identificados: list[str] | None = None,
) -> str:
    especificaciones_escapadas = (
        especificaciones
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    seccion_campos_html = ""
    if campos_identificados:
        etiquetas = resolver_etiquetas(campos_identificados)
        items = "".join(f"<li>{e}</li>" for e in etiquetas)
        seccion_campos_html = (
            '<p style="font-weight:700; margin-bottom: 6px;">Campos que requieren corrección:</p>'
            f'<ul style="margin: 0 0 16px; padding-left: 20px; color: #92400e;">{items}</ul>'
        )

    seccion_enlace_html = (
        f'<p style="text-align:center; margin: 24px 0;">'
        f'<a href="{enlace}" '
        f'style="background:#1d4ed8; color:#fff; padding:12px 28px; border-radius:6px; '
        f'text-decoration:none; font-weight:700; font-size:0.95em;">'
        f'Acceder al formulario</a></p>'
        if enlace
        else '<p>Por favor acceda al portal para realizar las correcciones solicitadas.</p>'
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1d4ed8; margin-bottom: 4px;">Formulario SAGRILAFT</h2>
  <p style="color: #64748b; margin-top: 0; font-size: 0.9em;">Requiere correcciones</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;">
  <p>Estimado usuario,</p>
  <p>Usted ha sido requerido para completar/modificar la siguiente información del formulario:</p>
  <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 4px; margin: 16px 0; white-space: pre-wrap;">
    {especificaciones_escapadas}
  </div>
  {seccion_campos_html}
  {seccion_enlace_html}
  <p style="color: #64748b; font-size: 0.85em; margin-top: 32px;">Equipo SAGRILAFT</p>
</body>
</html>"""
