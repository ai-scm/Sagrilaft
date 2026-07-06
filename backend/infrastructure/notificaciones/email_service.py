"""
EmailService — envío de correos transaccionales del sistema SAGRILAFT.

Es un no-op silencioso si SMTP no está configurado, para no bloquear flujos
de trabajo en entornos sin correo (desarrollo local, staging sin SMTP, etc.).
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from infrastructure.configuracion import SmtpConfig
from domain.catalogo_correcciones import resolver_etiquetas_campos_corregibles

logger = logging.getLogger(__name__)


class CorreoDestinatarioVacioError(Exception):
    """No se puede enviar notificación: el correo destinatario está vacío o es None."""
    
    def __init__(self, tipo_notificacion: str) -> None:
        super().__init__(
            f"No se puede enviar notificación de {tipo_notificacion}: "
            "correo destinatario es requerido y no está registrado."
        )


class EmailService:
    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    def _smtp_configurado(self) -> bool:
        return bool(self._config.host and self._config.usuario)
    
    def _validar_correo_destinatario(self, correo: str | None, tipo_notificacion: str) -> None:
        """
        Valida que el correo destinatario sea válido (no vacío ni None).
        
        Raises:
            CorreoDestinatarioVacioError: si correo es None o está vacío.
        """
        if not correo or not correo.strip():
            raise CorreoDestinatarioVacioError(tipo_notificacion)

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
        
        Raises:
            CorreoDestinatarioVacioError: si correo_destinatario es None o vacío.

        Returns:
            True si el correo se envió correctamente; False si SMTP no está
            configurado o si ocurrió un error de envío (no lanza excepción).
        """
        self._validar_correo_destinatario(correo_destinatario, "devolución")
        
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

    def enviar_notificacion_rechazo(
        self,
        correo_destinatario: str,
        mensaje_para_destinatario: str,
    ) -> bool:
        """
        Notifica al destinatario que su formulario SAGRILAFT fue rechazado.

        El mensaje lo redacta el operador; nunca incluye el motivo interno
        de compliance. Es un no-op silencioso si SMTP no está configurado.
        
        Raises:
            CorreoDestinatarioVacioError: si correo_destinatario es None o vacío.

        Returns:
            True si el correo se envió correctamente; False en caso contrario.
        """
        self._validar_correo_destinatario(correo_destinatario, "rechazo")
        
        if not self._smtp_configurado():
            logger.warning(
                "SMTP no configurado — se omite notificación de rechazo a '%s'.",
                correo_destinatario,
            )
            return False

        remitente = self._config.remitente or self._config.usuario
        mensaje = _construir_mensaje(
            remitente=remitente,
            destinatario=correo_destinatario,
            asunto="Formulario SAGRILAFT — Proceso finalizado",
            cuerpo_texto=_construir_cuerpo_texto_rechazo(mensaje_para_destinatario),
            cuerpo_html=_construir_cuerpo_html_rechazo(mensaje_para_destinatario),
        )
        return self._enviar(mensaje, correo_destinatario)

    def enviar_notificacion_actualizacion_reabierta(
        self,
        correo_destinatario: str,
        observaciones: str,
        enlace_diligenciamiento: str | None = None,
    ) -> bool:
        """
        Notifica al destinatario que su expediente quedó habilitado para una
        nueva actualización periódica.
        """
        self._validar_correo_destinatario(correo_destinatario, "actualización reabierta")

        if not self._smtp_configurado():
            logger.warning(
                "SMTP no configurado — se omite notificación de actualización reabierta a '%s'.",
                correo_destinatario,
            )
            return False

        remitente = self._config.remitente or self._config.usuario
        mensaje = _construir_mensaje(
            remitente=remitente,
            destinatario=correo_destinatario,
            asunto="Formulario SAGRILAFT — Actualización habilitada",
            cuerpo_texto=_construir_cuerpo_texto_actualizacion_reabierta(
                observaciones, enlace_diligenciamiento,
            ),
            cuerpo_html=_construir_cuerpo_html_actualizacion_reabierta(
                observaciones, enlace_diligenciamiento,
            ),
        )
        return self._enviar(mensaje, correo_destinatario)

    def enviar_notificacion_acceso_creado(
        self,
        correo_destinatario: str,
        codigo_peticion: str,
        pin: str,
        fecha_validez: str,
        enlace_diligenciamiento: str,
        razon_social: str,
    ) -> bool:
        """
        Envía al destinatario las credenciales del acceso manual recién creado.

        Es la única vez que el PIN viaja en texto plano fuera del portal interno;
        el cuerpo del correo advierte que no debe compartirse con terceros.

        Raises:
            CorreoDestinatarioVacioError: si correo_destinatario es None o vacío.

        Returns:
            True si el correo se envió correctamente; False en caso contrario.
        """
        self._validar_correo_destinatario(correo_destinatario, "acceso creado")

        if not self._smtp_configurado():
            logger.warning(
                "SMTP no configurado — se omite notificación de acceso creado a '%s'.",
                correo_destinatario,
            )
            return False

        remitente = self._config.remitente or self._config.usuario
        mensaje = _construir_mensaje(
            remitente=remitente,
            destinatario=correo_destinatario,
            asunto="SAGRILAFT — Credenciales de acceso a su formulario",
            cuerpo_texto=_construir_cuerpo_texto_acceso_creado(
                razon_social, codigo_peticion, pin, fecha_validez, enlace_diligenciamiento,
            ),
            cuerpo_html=_construir_cuerpo_html_acceso_creado(
                razon_social, codigo_peticion, pin, fecha_validez, enlace_diligenciamiento,
            ),
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
            logger.info("Notificación enviada a '%s'.", destinatario)
            return True
        except Exception:
            logger.exception(
                "Error al enviar notificación a '%s'.", destinatario
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
        etiquetas = resolver_etiquetas_campos_corregibles(campos_identificados)
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


def _construir_cuerpo_texto_rechazo(mensaje_para_destinatario: str) -> str:
    return (
        "Estimado usuario,\n\n"
        "Le informamos que el proceso de su formulario SAGRILAFT ha concluido.\n\n"
        f"{mensaje_para_destinatario}\n\n"
        "Equipo SAGRILAFT"
    )


def _construir_cuerpo_texto_actualizacion_reabierta(
    observaciones: str,
    enlace: str | None,
) -> str:
    seccion_enlace = (
        f"\nAcceda aquí para actualizar la información:\n{enlace}\n"
        if enlace
        else "\nPor favor acceda al portal para actualizar la información solicitada.\n"
    )
    return (
        "Estimado usuario,\n\n"
        "Su expediente SAGRILAFT fue habilitado nuevamente para actualización.\n\n"
        "Puede revisar y actualizar la información del cliente/proveedor, completar "
        "nuevos cuestionarios y cargar documentos adicionales.\n\n"
        f"Observaciones:\n{observaciones}\n"
        f"{seccion_enlace}\n"
        "Equipo SAGRILAFT"
    )


def _construir_cuerpo_html_rechazo(mensaje_para_destinatario: str) -> str:
    mensaje_escapado = (
        mensaje_para_destinatario
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #475569; margin-bottom: 4px;">Formulario SAGRILAFT</h2>
  <p style="color: #64748b; margin-top: 0; font-size: 0.9em;">Proceso finalizado</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;">
  <p>Estimado usuario,</p>
  <p>Le informamos que el proceso de su formulario SAGRILAFT ha concluido.</p>
  <div style="background: #f8fafc; border-left: 4px solid #94a3b8; padding: 16px; border-radius: 4px; margin: 16px 0; white-space: pre-wrap; color: #334155;">
    {mensaje_escapado}
  </div>
  <p style="color: #64748b; font-size: 0.85em; margin-top: 32px;">Equipo SAGRILAFT</p>
</body>
</html>"""


def _construir_cuerpo_html_actualizacion_reabierta(
    observaciones: str,
    enlace: str | None,
) -> str:
    observaciones_escapadas = (
        observaciones
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    seccion_enlace_html = (
        f'<p style="text-align:center; margin: 24px 0;">'
        f'<a href="{enlace}" '
        f'style="background:#0f766e; color:#fff; padding:12px 28px; border-radius:6px; '
        f'text-decoration:none; font-weight:700; font-size:0.95em;">'
        f'Actualizar expediente</a></p>'
        if enlace
        else '<p>Por favor acceda al portal para actualizar la información solicitada.</p>'
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #0f766e; margin-bottom: 4px;">Formulario SAGRILAFT</h2>
  <p style="color: #64748b; margin-top: 0; font-size: 0.9em;">Actualización habilitada</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;">
  <p>Estimado usuario,</p>
  <p>Su expediente SAGRILAFT fue habilitado nuevamente para actualización.</p>
  <p>Puede revisar y actualizar la información del cliente/proveedor, completar nuevos cuestionarios y cargar documentos adicionales.</p>
  <div style="background: #ecfdf5; border-left: 4px solid #0f766e; padding: 16px; border-radius: 4px; margin: 16px 0; white-space: pre-wrap;">
    {observaciones_escapadas}
  </div>
  {seccion_enlace_html}
  <p style="color: #64748b; font-size: 0.85em; margin-top: 32px;">Equipo SAGRILAFT</p>
</body>
</html>"""


def _construir_cuerpo_texto_acceso_creado(
    razon_social: str,
    codigo_peticion: str,
    pin: str,
    fecha_validez: str,
    enlace: str,
) -> str:
    return (
        "Estimado usuario,\n\n"
        f"Se ha generado un acceso al formulario SAGRILAFT para '{razon_social}'. "
        "Utilice las siguientes credenciales para recuperar autoguardado:\n\n"
        f"  Código de petición: {codigo_peticion}\n"
        f"  PIN de acceso:      {pin}\n"
        f"  Válido hasta:       {fecha_validez}\n\n"
        f"Acceda aquí para iniciar el diligenciamiento:\n{enlace}\n\n"
        "Este PIN es de uso personal: no lo comparta con terceros. Si usted no "
        "solicitó este acceso, ignore este mensaje.\n\n"
        "Equipo SAGRILAFT"
    )


def _construir_cuerpo_html_acceso_creado(
    razon_social: str,
    codigo_peticion: str,
    pin: str,
    fecha_validez: str,
    enlace: str,
) -> str:
    razon_social_esc = (
        razon_social
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1d4ed8; margin-bottom: 4px;">Formulario SAGRILAFT</h2>
  <p style="color: #64748b; margin-top: 0; font-size: 0.9em;">Credenciales de acceso</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;">
  <p>Estimado usuario,</p>
  <p>Se ha generado un acceso al formulario SAGRILAFT para <strong>{razon_social_esc}</strong>. Utilice las siguientes credenciales para diligenciarlo:</p>
  <div style="background: #f1f5f9; border-left: 4px solid #1d4ed8; padding: 16px; border-radius: 4px; margin: 16px 0;">
    <p style="margin: 0 0 8px;"><strong>Código de petición:</strong> {codigo_peticion}</p>
    <p style="margin: 0 0 8px;"><strong>PIN de acceso:</strong> {pin}</p>
    <p style="margin: 0;"><strong>Válido hasta:</strong> {fecha_validez}</p>
  </div>
  <p style="text-align:center; margin: 24px 0;">
    <a href="{enlace}" style="background:#1d4ed8; color:#fff; padding:12px 28px; border-radius:6px; text-decoration:none; font-weight:700; font-size:0.95em;">
      Diligenciar formulario</a>
  </p>
  <p style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; font-size: 0.85em; color: #78350f;">
    Este PIN es de uso personal: no lo comparta con terceros. Si usted no solicitó este acceso, ignore este mensaje.
  </p>
  <p style="color: #64748b; font-size: 0.85em; margin-top: 32px;">Equipo SAGRILAFT</p>
</body>
</html>"""


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
        etiquetas = resolver_etiquetas_campos_corregibles(campos_identificados)
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
