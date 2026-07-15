"""
RendereadorReporteService — generación de reportes en HTML y PDF.

Responsabilidades:
  - Generar HTML para reportes de comparación.
  - Generar PDF desde HTML (WeasyPrint).
  - Formateo de comparaciones para presentación.
"""

from datetime import datetime, timezone
from html import escape
from typing import Any, Dict

from services.expedientes.configuracion_campos_complejos import (
    ConfiguracionCamposComplejos,
)
from services.expedientes.reportes.generador_fichas import (
    generar_fichas_registro_comparadas,
)

_ETIQUETAS_CLASIFICACION_ACTIVIDAD = {
    "C": "Comercializador (C)",
    "D": "Distribuidor autorizado (D)",
    "R": "Representante (R)",
    "F": "Fabricante (F)",
    "I": "Importador (I)",
}

def _formatear_valor_simple(campo: str, valor: Any) -> str:
    """Formatea valores simples para presentación, como clasificaciones."""
    if valor is None:
        return ""
    valor_str = str(valor)
    if campo in ("actividad_clasificacion", "clasificacion_actividad"):
        return _ETIQUETAS_CLASIFICACION_ACTIVIDAD.get(valor_str, valor_str)
    return valor_str


class RendereadorReporteService:
    """
    Servicio de renderizado de reportes.

    Responsabilidades:
      - Generar HTML desde comparación de versiones.
      - Generar PDF desde HTML.
      - Usar configuración de campos complejos.
    """

    def __init__(self, configuracion: ConfiguracionCamposComplejos):
        """
        Inicializa el renderizador con configuración de campos.
        
        Argumentos:
            configuracion: ConfiguracionCamposComplejos para campos complejos
        """
        self._config = configuracion

    def generar_reporte_pdf(
        self,
        formulario: Any,
        comparacion: Dict[str, Any],
    ) -> bytes:
        """Genera un PDF con el reporte de comparación de cambios."""
        html = self._generar_html_reporte(formulario, comparacion)

        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RuntimeError("No se encontró 'weasyprint' para generar el PDF de comparación.") from exc

        return HTML(string=html).write_pdf()

    # ─── Privados ─────────────────────────────────────────────────────────────

    def _generar_html_reporte(
        self,
        formulario: Any,
        comparacion: Dict[str, Any],
    ) -> str:
        """Genera HTML para reporte de comparación de cambios."""
        generadoEn = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        filasHtml = []
        for cambio in comparacion["cambios"]:
            if self._config.es_campo_complejo(cambio["campo"]):
                fichasHtml = generar_fichas_registro_comparadas(
                    cambio["campo"],
                    cambio["valor_anterior"],
                    cambio["valor_corregido"],
                    self._config,
                )
                filasHtml.append(f'''
            <tr>
              <td colspan="3" style="padding: 0; border: none;">
                <div style="padding: 10px 8px;">
                  <div style="font-weight: bold; color: #0f172a; margin-bottom: 10px;">{escape(cambio["etiqueta"])}</div>
                  {fichasHtml}
                </div>
              </td>
            </tr>
            ''')
            else:
                valor_ant_fmt = _formatear_valor_simple(cambio["campo"], cambio["valor_anterior"])
                valor_cor_fmt = _formatear_valor_simple(cambio["campo"], cambio["valor_corregido"])
                filasHtml.append(f'''
            <tr>
              <td>{escape(cambio["etiqueta"])}</td>
              <td>{escape(valor_ant_fmt)}</td>
              <td>{escape(valor_cor_fmt)}</td>
            </tr>
            ''')

        contenidoFilas = "".join(filasHtml)
        if not contenidoFilas:
            mensajeVacio = comparacion.get("motivo") or "No se detectaron cambios en los campos comparables."
            contenidoFilas = f'<tr><td colspan="3" class="sin-cambios">{escape(mensajeVacio)}</td></tr>'

        return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; color: #0f172a; font-size: 12px; }}
        h1 {{ font-size: 20px; margin: 0 0 6px; }}
        .meta {{ color: #64748b; margin-bottom: 18px; }}
        .resumen {{ margin: 14px 0 18px; padding: 10px 12px; border: 1px solid #e2e8f0; background: #f8fafc; }}
        table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        th {{ text-align: left; background: #f1f5f9; color: #475569; font-size: 10px; text-transform: uppercase; padding: 8px; }}
        td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; vertical-align: top; word-wrap: break-word; }}
        .sin-cambios {{ text-align: center; color: #64748b; padding: 18px; }}
      </style>
    </head>
    <body>
      <h1>Evidencia de cambios corregidos</h1>
      <div class="meta">Generado: {escape(generadoEn)}</div>
      <div class="resumen">
        <strong>Expediente:</strong> {escape(formulario.codigo_peticion or formulario.id)}<br>
        <strong>Razón social:</strong> {escape(formulario.razon_social or "Sin información")}<br>
        <strong>Comparación:</strong> v{comparacion["version_anterior"]} → v{comparacion["version_corregida"]}<br>
        <strong>Total de cambios:</strong> {comparacion["total_cambios"]}
      </div>
      <table>
        <thead>
          <tr>
            <th>Campo</th>
            <th>Antes</th>
            <th>Después</th>
          </tr>
        </thead>
        <tbody>{contenidoFilas}</tbody>
      </table>
    </body>
    </html>
    """
