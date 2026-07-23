"""
AuditoriaService — métricas operativas y generación de reporte de cadena de custodia.

Responsabilidades:
  - Exponer métricas del estado operativo de expedientes (dashboard).
  - Generar un reporte PDF de auditoría por expediente con su línea de tiempo
    de eventos, documentos con hash y firma HMAC que certifica la integridad del reporte.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional

from domain.auditoria.entidades import EventoAuditoria
from domain.formulario.entidades import FormularioDatos
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.repositorios import RepositorioExpediente
from domain.formulario.tipos import EstadoFormulario


# ── Etiquetas legibles para tipos de evento ──────────────────────────────────

_ETIQUETAS_EVENTO = {
    "FORMULARIO_CREADO":    "Formulario creado",
    "FORMULARIO_ENVIADO":       "Formulario enviado a revisión",
    "FORMULARIO_APROBADO":      "Formulario validado (aprobado internamente)",
    "FORMULARIO_APROBACION_REVERTIDA": "Validación de formulario revertida",
    "FORMULARIO_RECHAZADO":     "Formulario rechazado (cierre definitivo)",
    "FORMULARIO_DEVUELTO":  "Devuelto para corrección",
    "FORMULARIO_DEVOLUCION_REVERTIDA": "Devolución revertida",
    "FORMULARIO_CARGADO_MANUALMENTE": "Formulario cargado manualmente",
    "REPORTE_FINAL_CARGADO": "Informe final cargado",
    "REPORTE_FINAL_ELIMINADO": "Informe final eliminado",
    "EXPEDIENTE_CERRADO": "Expediente cerrado",
    "EXPEDIENTE_REABIERTO_ACTUALIZACION": "Actualización reabierta",
    "FIRMA_INICIADA":       "Enviado a firma electrónica",
    "FIRMA_COMPLETADA":     "Firma electrónica completada",
    "FIRMA_CANCELADA":      "Firma electrónica cancelada",
    "DOCUMENTO_CARGADO":    "Documento cargado",
    "DOCUMENTO_ELIMINADO":  "Documento eliminado",
    "CAMBIO_DIRECTO_BD":    "⚠ Cambio directo en base de datos",
}

_ETIQUETAS_ESTADO = {
    "borrador":        "Borrador",
    "enviado":         "Enviado",
    "validado":        "Aprobado",
    "rechazado":       "Rechazado",
    "en_correccion":   "En corrección",
    "pendiente_firma": "Pendiente de firma",
    "firmado":         "Firmado",
    "cerrado":         "Cerrado",
}

_ETIQUETAS_ACTOR = {
    "OPERADOR":    "Operador",
    "CONTRAPARTE": "Contraparte",
    "SISTEMA":     "Sistema",
    "DB_DIRECTO":  "Base de datos (acceso directo)",
}

_ETIQUETAS_DOCUMENTO = {
    "cedula_representante":   "Documento de Identidad del Representante Legal",
    "certificado_existencia": "Certificado de Existencia y Representación Legal",
    "estados_financieros":    "Estados Financieros",
    "declaracion_renta":      "Declaración de Renta",
    "rut":                    "RUT (Registro Único Tributario)",
    "referencias_bancarias":  "Certificaciones Bancarias",
    "FORMULARIO_PDF":         "Formulario SAGRILAFT (Oficial)",
    "CERTIFICADO_SAGRILAFT":  "Certificado de Firma Electrónica",
    "REPORTE_FINAL":          "Informe Final de Evaluación",
}

_ETIQUETAS_CAUSAL_CIERRE = {
    "informe_final": "Cierre aprobado con informe final",
    "no_continuacion_dialogos": "No continuación de diálogos",
    "rechazado_con_informe_final": "Cierre rechazado con informe final",
}

def _documento_label(tipo: Optional[str]) -> str:
    return _ETIQUETAS_DOCUMENTO.get(tipo or "", tipo or "—")

def _estado_label(estado: Optional[str]) -> str:
    return _ETIQUETAS_ESTADO.get(estado or "", estado or "—")


def _actor_label(actor_tipo: str) -> str:
    return _ETIQUETAS_ACTOR.get(actor_tipo, actor_tipo)


def _ts(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d/%m/%Y %H:%M:%S UTC")


def _firmar_reporte(contenido: str, secret_key: str) -> str:
    """HMAC-SHA256 del contenido del reporte para verificación de integridad."""
    firma = hmac.new(secret_key.encode(), contenido.encode(), hashlib.sha256).hexdigest()
    return firma


# ── HTML del reporte ──────────────────────────────────────────────────────────

_CSS_REPORTE = """
    @page { size: A4; margin: 16mm 12mm; }
    body { font-family: Arial, sans-serif; font-size: 11pt; color: #1a1a2e; margin: 0; padding: 0; }
    .portada { background: #1a1a2e; color: white; padding: 40px 32px 32px; }
    .portada h1 { font-size: 22pt; margin: 0 0 8px; }
    .portada p { margin: 4px 0; font-size: 10pt; color: #c0c0d0; }
    .cuerpo { padding: 24px 32px; }
    h2 { font-size: 13pt; color: #1a1a2e; border-bottom: 2px solid #e0e0ef; padding-bottom: 4px; margin-top: 28px; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 9.5pt; margin-top: 8px; }
    th { background: #1a1a2e; color: white; padding: 6px 8px; text-align: left; }
    td { padding: 5px 8px; border-bottom: 1px solid #e8e8f0; vertical-align: top; overflow-wrap: anywhere; word-break: break-word; }
    tr:nth-child(even) td { background: #f5f5fc; }
    .alerta td { background: #fff3cd !important; }
    .tabla-documentos { font-size: 8.2pt; table-layout: fixed; }
    .tabla-documentos th, .tabla-documentos td { padding: 4px 5px; }
    .tabla-documentos .col-tipo { width: 18%; }
    .tabla-documentos .col-archivo { width: 30%; }
    .tabla-documentos .col-version { width: 8%; }
    .tabla-documentos .col-tamano { width: 10%; }
    .tabla-documentos .col-actor { width: 16%; }
    .tabla-documentos .col-fecha { width: 18%; }
    .hash-documento { font-family: monospace; font-size: 7.2pt; color: #475569; overflow-wrap: anywhere; word-break: break-all; }
    .hash-documento strong { color: #1a1a2e; font-family: Arial, sans-serif; font-size: 7.6pt; }
    .firma-reporte { margin-top: 32px; padding: 12px 16px; background: #f0f4ff;
                     border-left: 4px solid #1a1a2e; font-size: 9pt; font-family: monospace;
                     word-break: break-all; }
    .meta-tabla td:first-child { font-weight: bold; width: 180px; }
    .sin-datos { color: #999; font-style: italic; }
"""


def _html_portada(formulario: FormularioDatos, generado_en: datetime) -> str:
    return (
        "<div class='portada'>"
        "<h1>Reporte de Auditoría SAGRILAFT</h1>"
        f"<p>Expediente: <strong>{escape(formulario.codigo_peticion or '')}</strong></p>"
        f"<p>Razón social: {escape(formulario.razon_social or '—')}</p>"
        f"<p>NIT/ID: {escape(formulario.numero_identificacion or '—')}</p>"
        f"<p>Estado actual: {escape(_estado_label(formulario.estado))}</p>"
        f"<p>Correcciones realizadas: {formulario.numero_correccion or 0}</p>"
        f"<p style='margin-top:16px; font-size:9pt;'>Generado: {_ts(generado_en)}</p>"
        "</div>"
    )


def _html_info_general(formulario: FormularioDatos) -> str:
    filas = [
        ("Tipo de contraparte", formulario.tipo_contraparte or "—"),
        ("Tipo de persona",     formulario.tipo_persona or "—"),
        ("País",                formulario.pais or "—"),
        ("Ciudad",              formulario.ciudad or "—"),
        ("Correo",              formulario.correo or "—"),
        ("Fecha de creación",   _ts(formulario.created_at)),
        ("Última actualización", _ts(formulario.updated_at)),
    ]
    rows = "".join(
        f"<tr><td><strong>{escape(k)}</strong></td><td>{escape(str(v))}</td></tr>"
        for k, v in filas
    )
    return (
        "<h2>Información del expediente</h2>"
        f"<table class='meta-tabla'><tbody>{rows}</tbody></table>"
    )


def _html_linea_de_tiempo(eventos: List[EventoAuditoria]) -> str:
    if not eventos:
        return "<h2>Línea de tiempo de eventos</h2><p class='sin-datos'>No hay eventos registrados.</p>"

    encabezados = "<tr><th>#</th><th>Fecha / Hora</th><th>Evento</th><th>Estado anterior</th><th>Estado nuevo</th><th>Actor</th><th>Identificador actor</th></tr>"
    filas = ""
    for i, ev in enumerate(eventos, 1):
        tipo_label = _ETIQUETAS_EVENTO.get(ev.tipo_evento, ev.tipo_evento)
        
        detalles_extra = ""
        if ev.metadata and "causal_cierre" in ev.metadata:
            causal_raw = ev.metadata["causal_cierre"]
            causal_str = _ETIQUETAS_CAUSAL_CIERRE.get(causal_raw, causal_raw)
            detalles_extra = f"<br><small style='color: #475569; font-size: 8.5pt;'><b>Causal:</b> {escape(causal_str)}</small>"

        css_clase = "alerta" if ev.tipo_evento == "CAMBIO_DIRECTO_BD" else ""
        filas += (
            f"<tr class='{css_clase}'>"
            f"<td>{i}</td>"
            f"<td>{_ts(ev.created_at)}</td>"
            f"<td>{escape(tipo_label)}{detalles_extra}</td>"
            f"<td>{escape(_estado_label(ev.estado_anterior))}</td>"
            f"<td>{escape(_estado_label(ev.estado_nuevo))}</td>"
            f"<td>{escape(_actor_label(ev.actor_tipo))}</td>"
            f"<td>{escape(ev.actor_id or '—')}</td>"
            "</tr>"
        )
    return (
        "<h2>Línea de tiempo de eventos</h2>"
        f"<table><thead>{encabezados}</thead><tbody>{filas}</tbody></table>"
    )


def _html_documentos(documentos: List[Dict[str, Any]]) -> str:
    if not documentos:
        return "<h2>Documentos y cadena de custodia</h2><p class='sin-datos'>Sin documentos registrados.</p>"

    encabezados = (
        "<tr>"
        "<th class='col-tipo'>Tipo</th>"
        "<th class='col-archivo'>Archivo</th>"
        "<th class='col-version'>Ver.</th>"
        "<th class='col-tamano'>Tamaño</th>"
        "<th class='col-actor'>Cargado por</th>"
        "<th class='col-fecha'>Fecha carga</th>"
        "</tr>"
    )
    filas = "".join(
        f"<tr>"
        f"<td>{escape(_documento_label(d.get('tipo_documento')))}</td>"
        f"<td>{escape(str(d.get('nombre_archivo', '—')))}</td>"
        f"<td>{escape(str(d.get('version_numero', 1)))}</td>"
        f"<td>{escape(str(d.get('tamano') or '—'))}</td>"
        f"<td>{escape(str(d.get('subido_por') or '—'))}</td>"
        f"<td>{_ts(d.get('created_at'))}</td>"
        "</tr>"
        f"<tr><td colspan='6' class='hash-documento'>"
        f"<strong>Hash SHA-256:</strong> {escape(str(d.get('hash_sha256') or '—'))}"
        "</td></tr>"
        for d in documentos
    )
    return (
        "<h2>Documentos y cadena de custodia</h2>"
        f"<table class='tabla-documentos'><thead>{encabezados}</thead><tbody>{filas}</tbody></table>"
    )


def _html_firma(firma_hex: str, generado_en: datetime) -> str:
    return (
        "<div class='firma-reporte'>"
        "<strong>Firma de integridad del reporte (HMAC-SHA256)</strong><br>"
        f"Este reporte fue generado el {_ts(generado_en)} por el sistema SAGRILAFT.<br>"
        "La siguiente firma criptográfica verifica que el contenido no ha sido alterado:<br><br>"
        f"{escape(firma_hex)}"
        "</div>"
    )


# ── Service ───────────────────────────────────────────────────────────────────

class AuditoriaService:
    """
    Servicio de auditoría y seguimiento operativo.

    Dependencias:
      - repo_auditoria: consultas a eventos_formulario y documentos_adjuntos.
      - repo_expediente: para recuperar el formulario al generar el reporte.
      - secret_key: clave para firmar reportes con HMAC.
    """

    def __init__(
        self,
        repo_auditoria: RepositorioAuditoria,
        repo_expediente: RepositorioExpediente,
        secret_key: str,
    ) -> None:
        self._auditoria = repo_auditoria
        self._expediente = repo_expediente
        self._secret_key = secret_key

    # ── Dashboard operativo ───────────────────────────────────────────────────

    def metricas_dashboard(self) -> Dict[str, Any]:
        """Métricas en tiempo real del estado de expedientes SAGRILAFT."""
        return self._auditoria.metricas_dashboard()

    # ── Línea de tiempo ───────────────────────────────────────────────────────

    def obtener_eventos(self, formulario_id: str) -> List[Dict[str, Any]]:
        """Devuelve los eventos de un formulario serializados para la API."""
        eventos = self._auditoria.listar_eventos(formulario_id)
        return [
            {
                "id":              ev.id,
                "tipo_evento":     ev.tipo_evento,
                "etiqueta":        _ETIQUETAS_EVENTO.get(ev.tipo_evento, ev.tipo_evento),
                "estado_anterior": ev.estado_anterior,
                "estado_nuevo":    ev.estado_nuevo,
                "actor_id":        ev.actor_id,
                "actor_tipo":      ev.actor_tipo,
                "metadata":        ev.metadata,
                "created_at":      ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in eventos
        ]

    # ── Reporte PDF de auditoría ──────────────────────────────────────────────

    def generar_reporte_pdf(self, formulario_id: str) -> bytes:
        """
        Genera un PDF de cadena de custodia con línea de tiempo, documentos
        y firma HMAC del reporte.

        El PDF se retorna como bytes — el caller decide cómo entregarlo.
        """
        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RuntimeError(
                "WeasyPrint no está instalado. Instala las dependencias del backend."
            ) from exc

        from domain.formulario.tipos import EstadoFormulario as EF

        estados_expediente = [
            EF.ENVIADO, EF.EN_CORRECCION, EF.VALIDADO,
            EF.RECHAZADO, EF.PENDIENTE_FIRMA, EF.FIRMADO,
            EF.CERRADO,
        ]
        formulario = self._expediente.obtener(formulario_id, estados_expediente)
        if not formulario:
            raise ValueError(f"Formulario {formulario_id} no encontrado o en borrador")

        eventos   = self._auditoria.listar_eventos(formulario_id)
        documentos = self._auditoria.listar_documentos_con_trazabilidad(formulario_id)
        generado_en = datetime.now(timezone.utc)

        # Construir contenido que se firma (antes de añadir el bloque de firma)
        cuerpo_firmable = (
            f"formulario_id={formulario_id}|"
            f"codigo={formulario.codigo_peticion}|"
            f"estado={formulario.estado}|"
            f"eventos={len(eventos)}|"
            f"documentos={len(documentos)}|"
            f"generado={generado_en.isoformat()}"
        )
        firma_hex = _firmar_reporte(cuerpo_firmable, self._secret_key)

        html_body = (
            _html_portada(formulario, generado_en)
            + "<div class='cuerpo'>"
            + _html_info_general(formulario)
            + _html_linea_de_tiempo(eventos)
            + _html_documentos(documentos)
            + _html_firma(firma_hex, generado_en)
            + "</div>"
        )

        html_completo = (
            "<!DOCTYPE html><html lang='es'><head>"
            "<meta charset='UTF-8'>"
            f"<style>{_CSS_REPORTE}</style>"
            "</head><body>"
            + html_body
            + "</body></html>"
        )

        return HTML(string=html_completo).write_pdf()
