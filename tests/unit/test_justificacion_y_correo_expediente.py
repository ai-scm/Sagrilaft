"""Justificación de las acciones en el reporte de auditoría y correo de contacto del expediente."""

from types import SimpleNamespace

from domain.auditoria.entidades import EventoAuditoria
from services.auditoria.auditoria_service import _html_linea_de_tiempo, _justificacion_evento
from services.expedientes.expediente_service import ExpedienteService


def _evento(metadata):
    return EventoAuditoria(
        formulario_id="f-1",
        tipo_evento="EXPEDIENTE_CERRADO",
        estado_nuevo="CERRADO",
        actor_tipo="OPERADOR",
        estado_anterior="FIRMADO",
        actor_id="analista@empresa.com",
        metadata=metadata,
    )


def test_justificacion_sale_de_justificacion_o_de_upload_reason():
    assert _justificacion_evento({"justificacion": "  No continúa  "}) == "No continúa"
    assert _justificacion_evento({"upload_reason": "Informe aprobado"}) == "Informe aprobado"
    assert _justificacion_evento({"justificacion": "", "upload_reason": ""}) == ""
    assert _justificacion_evento(None) == ""
    assert _justificacion_evento({"justificacion": 123}) == ""


def test_reporte_muestra_la_justificacion_escapada_bajo_la_causal():
    html = _html_linea_de_tiempo([
        _evento({"causal_cierre": "no_continuacion_dialogos", "justificacion": "Sin respuesta <b>x</b>"}),
    ])

    assert "<b>Causal:</b>" in html
    assert "<b>Justificación:</b> Sin respuesta &lt;b&gt;x&lt;/b&gt;" in html


def test_reporte_no_agrega_justificacion_vacia():
    html = _html_linea_de_tiempo([_evento({"causal_cierre": "no_continuacion_dialogos", "justificacion": ""})])

    assert "Justificación" not in html


def test_correo_de_contacto_prefiere_el_del_acceso():
    formulario = SimpleNamespace(correo_representante="formulario@empresa.com")

    assert ExpedienteService._correo_contacto(formulario, "acceso@empresa.com") == "acceso@empresa.com"
    assert ExpedienteService._correo_contacto(formulario, None) == "formulario@empresa.com"
    assert ExpedienteService._correo_contacto(SimpleNamespace(correo_representante=None), None) is None
