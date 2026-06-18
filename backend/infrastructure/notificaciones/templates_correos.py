"""
Templates HTML para notificaciones transaccionales del sistema SAGRILAFT.

Ventajas:
  - Centraliza diseño y estilos CSS para mantenimiento consistente
  - Reutilizable en SNS, email directo y futuras integraciones
  - Lenguaje ubicuo en español con terminología del dominio
  - Responsive design: desktop, tablet, móvil
  - Accesibilidad WCAG AA
  - Sin duplicación de código
"""

from typing import Dict, Optional
from enum import Enum
from datetime import datetime, timezone


class TipoAlertaTemplate(str, Enum):
    """Tipos de alertas y sus atributos visuales."""
    FORMULARIO_RECIBIDO = "FORMULARIO_RECIBIDO"
    FORMULARIO_DEVUELTO = "FORMULARIO_DEVUELTO"
    FORMULARIO_CORREGIDO = "FORMULARIO_CORREGIDO"
    FORMULARIO_ENVIADO_A_FIRMA = "FORMULARIO_ENVIADO_A_FIRMA"
    FORMULARIO_FIRMADO = "FORMULARIO_FIRMADO"
    FORMULARIO_RECHAZADO = "FORMULARIO_RECHAZADO"
    REPORTE_FINAL_CARGADO = "REPORTE_FINAL_CARGADO"


# ── Configuración por tipo de alerta ─────────────────────────────────────────

CONFIGURACION_ALERTA: Dict[TipoAlertaTemplate, Dict[str, str]] = {
    TipoAlertaTemplate.FORMULARIO_RECIBIDO: {
        "titulo": "Nuevo Formulario Recibido",
        "icono": "&#x1F4CB;",  # 📋 (clipboard) - usar entity HTML para evitar markdown conversion
        "color": "#1d4ed8",  # Azul
        "color_oscuro": "#1e40af",
        "mensaje": "Se ha recibido un nuevo formulario que requiere revisión y gestión en el portal SAGRILAFT.",
        "etiqueta_boton": "Revisar Formulario en el Portal",
    },
    TipoAlertaTemplate.FORMULARIO_DEVUELTO: {
        "titulo": "Formulario Devuelto para Corrección",
        "icono": "&#x26A0;",  # ⚠️ (warning) - usar entity HTML para evitar markdown conversion
        "color": "#f59e0b",  # Ámbar
        "color_oscuro": "#d97706",
        "mensaje": "El formulario ha sido devuelto para realizar correcciones. Por favor, revise los detalles.",
        "etiqueta_boton": "Ver Correcciones Requeridas",
    },
    TipoAlertaTemplate.FORMULARIO_CORREGIDO: {
        "titulo": "Formulario Corregido Recibido",
        "icono": "&#x2705;",  # ✅ (checkmark) - usar entity HTML para evitar markdown conversion
        "color": "#10b981",  # Verde
        "color_oscuro": "#059669",
        "mensaje": "El formulario corregido ha sido recibido exitosamente. Revise los cambios en el portal.",
        "etiqueta_boton": "Ver Formulario Corregido",
    },
    TipoAlertaTemplate.FORMULARIO_ENVIADO_A_FIRMA: {
        "titulo": "Formulario Enviado a Firma Electrónica",
        "icono": "&#x270D;",  # ✍️ (writing hand) - usar entity HTML para evitar markdown conversion
        "color": "#8b5cf6",  # Púrpura
        "color_oscuro": "#7c3aed",
        "mensaje": "El formulario ha sido enviado a firma electrónica. Revise el estado en el portal.",
        "etiqueta_boton": "Ver Estado de Firma",
    },
    TipoAlertaTemplate.FORMULARIO_FIRMADO: {
        "titulo": "Formulario Firmado Electrónicamente",
        "icono": "&#x1F50F;",  # 🔏 (padlock) - usar entity HTML para evitar markdown conversion
        "color": "#06b6d4",  # Cyan
        "color_oscuro": "#0891b2",
        "mensaje": "El formulario ha sido firmado electrónicamente. Descargue la copia firmada en el portal.",
        "etiqueta_boton": "Descargar Formulario Firmado",
    },
    TipoAlertaTemplate.FORMULARIO_RECHAZADO: {
        "titulo": "Formulario Rechazado",
        "icono": "&#x274C;",  # ❌ (cross mark) - usar entity HTML para evitar markdown conversion
        "color": "#dc2626",  # Rojo
        "color_oscuro": "#b91c1c",
        "mensaje": "El expediente fue rechazado de forma definitiva. Revise el motivo interno y la trazabilidad en el portal.",
        "etiqueta_boton": "Ver Expediente Rechazado",
    },
    TipoAlertaTemplate.REPORTE_FINAL_CARGADO: {
        "titulo": "Reporte Final Cargado",
        "icono": "&#x1F4C4;",  # 📄 (documento) - usar entity HTML para evitar markdown conversion
        "color": "#0f766e",  # Teal
        "color_oscuro": "#115e59",
        "mensaje": "Se ha cargado el reporte final del expediente. La carpeta quedó cerrada para gestión interna.",
        "etiqueta_boton": "Ver Reporte Final en el Portal",
    },
}


def _escapar_html(texto: str | None) -> str:
    """Escapa caracteres HTML para prevenir XSS."""
    if not texto:
        return ""
    return (
        texto
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _construir_estilos_css(color_primario: str) -> str:
    """Construye hoja de estilos CSS responsiva y accesible."""
    return f"""
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      color: #1e293b;
      margin: 0;
      padding: 0;
      background: #f8fafc;
    }}
    .contenedor {{
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
    }}
    .envoltura-correo {{
      background: #ffffff;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      overflow: hidden;
    }}
    .encabezado {{
      background: linear-gradient(135deg, {color_primario}, {color_primario}dd);
      color: #ffffff;
      padding: 24px;
      text-align: center;
    }}
    .encabezado h1 {{
      margin: 0;
      font-size: 1.5em;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    .encabezado-subtitulo {{
      font-size: 0.9em;
      opacity: 0.95;
      margin-top: 4px;
    }}
    .contenido {{
      padding: 32px 24px;
    }}
    .contenido p {{
      line-height: 1.6;
      margin: 0 0 16px 0;
    }}
    .detalles {{
      background: #f1f5f9;
      border-left: 4px solid {color_primario};
      padding: 16px;
      border-radius: 4px;
      margin: 24px 0;
    }}
    .fila-detalle {{
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 12px;
      margin-bottom: 8px;
      font-size: 0.95em;
    }}
    .fila-detalle:last-child {{
      margin-bottom: 0;
    }}
    .etiqueta-detalle {{
      font-weight: 600;
      color: #475569;
    }}
    .valor-detalle {{
      color: #334155;
      word-break: break-all;
    }}
    .seccion-cta {{
      text-align: center;
      margin: 32px 0;
    }}
    .boton {{
      display: inline-block;
      background: {color_primario};
      color: #ffffff;
      padding: 14px 32px;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.95em;
      border: 2px solid {color_primario};
      transition: all 0.2s ease;
      width: 280px;
      box-sizing: border-box;
      cursor: pointer;
    }}
    .boton:hover {{
      filter: brightness(0.9);
      text-decoration: none;
    }}
    .boton:focus {{
      outline: 2px solid #000;
      outline-offset: 2px;
    }}
    .enlace-alternativo {{
      margin-top: 16px;
      font-size: 0.85em;
    }}
    .enlace-alternativo a {{
      color: {color_primario};
      text-decoration: underline;
      word-break: break-all;
    }}
    .acceso-manual {{
      background: #fef3c7;
      border-left: 4px solid #f59e0b;
      padding: 12px 16px;
      border-radius: 4px;
      margin-top: 16px;
      font-size: 0.9em;
      color: #78350f;
    }}
    .acceso-manual code {{
      background: #fde68a;
      padding: 2px 6px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
    }}
    .pie {{
      background: #f8fafc;
      border-top: 1px solid #e2e8f0;
      padding: 20px 24px;
      text-align: center;
      font-size: 0.85em;
      color: #64748b;
    }}
    .pie a {{
      color: {color_primario};
      text-decoration: none;
    }}
    .divisor-pie {{
      margin: 12px 0;
    }}
    @media (max-width: 600px) {{
      .contenedor {{
        padding: 0;
      }}
      .contenido {{
        padding: 20px 16px;
      }}
      .fila-detalle {{
        grid-template-columns: 100px 1fr;
      }}
      .boton {{
        width: 100%;
        padding: 12px 20px;
      }}
      .encabezado h1 {{
        font-size: 1.25em;
      }}
    }}
    .boton:focus-visible {{
      outline: 3px solid {color_primario};
      outline-offset: 2px;
    }}
"""


def _generar_seccion_cta_html(
    incluir_cta: bool,
    enlace_formulario: str,
    config: dict,
    codigo_peticion_esc: str,
) -> str:
    """
    Genera la sección CTA (Call-To-Action) en HTML de forma condicional.
    
    Cuando incluir_cta=True: incluye botón + enlace alternativo + acceso manual.
    Cuando incluir_cta=False: retorna string vacío para omitir toda la sección.
    
    Parámetros de dominio ubicuo:
      enlace_formulario: URL completa al expediente con parámetros UTM
      config: Diccionario de configuración de alerta (color, etiqueta_boton, etc.)
      codigo_peticion_esc: Código SAG-XXXXXXXX escapado para seguridad
    """
    if not incluir_cta:
        return ""
    
    return f"""
        <!-- Botón de acción principal (CTA) -->
        <div class="seccion-cta">
          <a href="{enlace_formulario}" class="boton" role="button" aria-label="Revisar formulario en el portal SAGRILAFT" style="background-color: {config['color']}; color: #ffffff; display: inline-block; padding: 14px 32px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.95em; border: 2px solid {config['color']}; border-radius: 6px; width: 280px; box-sizing: border-box; cursor: pointer; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            &#x2192; {config['etiqueta_boton']} &#x2190;
          </a>
          <div class="enlace-alternativo">
            O acceda directamente a: <a href="{enlace_formulario}">{enlace_formulario[:50]}...</a>
          </div>
        </div>

        <!-- Instrucción de acceso manual -->
        <div class="acceso-manual">
          <strong>Acceso manual:</strong> Ingrese el código de petición <code>{codigo_peticion_esc}</code> 
          en el portal de SAGRILAFT para localizar este formulario.
        </div>
"""


def construir_html_notificacion(
    tipo_alerta: TipoAlertaTemplate,
    formulario_id: str,
    razon_social: str,
    tipo_contraparte: str,
    codigo_peticion: Optional[str],
    url_portal: str,
    detalle: Optional[str] = None,
    incluir_cta: bool = True,
) -> str:
    """
    Construye el cuerpo HTML completo de la notificación.
    
    Parámetros:
      tipo_alerta: Tipo de evento (FORMULARIO_RECIBIDO, etc.)
      formulario_id: UUID del formulario
      razon_social: Nombre legal de la contraparte
      tipo_contraparte: 'cliente' o 'proveedor'
      codigo_peticion: Código único SAG-XXXXXXXX
      url_portal: URL base del portal interno (ej: https://portal.sagrilaft.com)
      detalle: Información adicional opcional
      incluir_cta: Si False, omite botón, enlace alternativo y acceso manual (para alertas internas)
    
    Retorna:
      String HTML completo y escapeado.
    """
    config = CONFIGURACION_ALERTA[tipo_alerta]
    
    # Construir URLs
    campaign_value = tipo_alerta.value.lower()
    enlace_formulario = (
        f"{url_portal}/expedientes/{formulario_id}"
        f"?utm_source=email&utm_medium=notification&utm_campaign={campaign_value}"
    )
    
    # Timestamp actual en formato legible
    timestamp = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    
    # Escapar valores para seguridad
    razon_social_esc = _escapar_html(razon_social)
    tipo_contraparte_esc = _escapar_html(tipo_contraparte.capitalize())
    codigo_peticion_esc = _escapar_html(codigo_peticion or "N/A")
    formulario_id_truncado = _escapar_html(formulario_id[:16] + "...")
    
    # Sección de detalle adicional (si existe)
    # Formatea el detalle para que preserva saltos de línea y viñetas en HTML
    seccion_detalle = ""
    if detalle:
        # Escapar HTML
        detalle_esc = _escapar_html(detalle)
        # Preservar saltos de línea: \n → <br>, • (viñeta) se mantiene
        detalle_formateado = detalle_esc.replace("\n", "<br>")
        seccion_detalle = f'<div style="color: #64748b; font-size: 0.9em; margin-top: 16px; line-height: 1.5;"><strong>Detalle:</strong><br>{detalle_formateado}</div>'
    
    # Estilos CSS
    estilos = _construir_estilos_css(config["color"])
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{config['titulo']}</title>
  <style>
    {estilos}
  </style>
</head>
<body>
  <div class="contenedor">
    <div class="envoltura-correo">
      <!-- Encabezado -->
      <div class="encabezado">
        <h1>{config['icono']} {config['titulo']}</h1>
        <div class="encabezado-subtitulo">SAGRILAFT — Portal de Gestión</div>
      </div>

      <!-- Contenido principal -->
      <div class="contenido">
        <p>Estimado usuario,</p>
        <p>{config['mensaje']}</p>

        <!-- Detalles del formulario -->
        <div class="detalles">
          <div class="fila-detalle">
            <span class="etiqueta-detalle">Razón Social:</span>
            <span class="valor-detalle">{razon_social_esc}</span>
          </div>
          <div class="fila-detalle">
            <span class="etiqueta-detalle">Tipo:</span>
            <span class="valor-detalle">{tipo_contraparte_esc}</span>
          </div>
          <div class="fila-detalle">
            <span class="etiqueta-detalle">Código Petición:</span>
            <span class="valor-detalle">{codigo_peticion_esc}</span>
          </div>
          <div class="fila-detalle">
            <span class="etiqueta-detalle">Recibido:</span>
            <span class="valor-detalle">{timestamp}</span>
          </div>
          <div class="fila-detalle">
            <span class="etiqueta-detalle">ID Formulario:</span>
            <span class="valor-detalle" title="{formulario_id}">{formulario_id_truncado}</span>
          </div>
        </div>

        {seccion_detalle}

        {_generar_seccion_cta_html(incluir_cta, enlace_formulario, config, codigo_peticion_esc)}

        <p style="color: #64748b; font-size: 0.9em; margin-top: 24px;">
          Si tiene preguntas o necesita asistencia, contáctenos a través del portal SAGRILAFT.
        </p>
      </div>

      <!-- Pie de página -->
      <div class="pie">
        <div>© 2026 SAGRILAFT — Sistema de Gestión de Riesgo de Lavado de Activos</div>
        <div class="divisor-pie"></div>
        <div>
          <a href="{url_portal}">Portal</a> | 
          <a href="{url_portal}/ayuda">Ayuda</a> | 
          <a href="{url_portal}/privacidad">Privacidad</a>
        </div>
      </div>
    </div>
  </div>
</body>
</html>"""
    return html


def construir_texto_plano_notificacion(
    tipo_alerta: TipoAlertaTemplate,
    formulario_id: str,
    razon_social: str,
    tipo_contraparte: str,
    codigo_peticion: Optional[str],
    url_portal: str,
    detalle: Optional[str] = None,
    incluir_cta: bool = True,
) -> str:
    """
    Construye versión en texto plano de la notificación.
    
    Se usa como fallback en clientes de correo sin soporte HTML,
    y para mensajes en SNS cuando no se usa MessageStructure="json".
    
    Parámetros:
      incluir_cta: Si False, omite URL de acceso al formulario y acceso manual.
    """
    timestamp = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    enlace = f"{url_portal}/expedientes/{formulario_id}"
    
    lineas = [
        f"Evento:           {tipo_alerta.value}",
        f"Fecha/Hora:       {timestamp}",
        f"Razón Social:     {razon_social}",
        f"Tipo contraparte: {tipo_contraparte}",
        f"Código petición:  {codigo_peticion or 'N/A'}",
        f"Formulario ID:    {formulario_id}",
    ]
    
    if detalle:
        lineas.append(f"Detalle:          {detalle}")
    
    if incluir_cta:
        lineas.extend([
            "",
            "─" * 60,
            "",
            "Acceda al formulario en:",
            enlace,
            "",
            f"O ingrese el código de petición ({codigo_peticion or 'N/A'})",
            "en el portal SAGRILAFT.",
        ])
    
    return "\n".join(lineas)
