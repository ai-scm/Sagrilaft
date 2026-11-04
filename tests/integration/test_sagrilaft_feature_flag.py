"""
Verifica de punta a punta que el feature flag PROVEEDOR_LISTAS_CAUTELA no solo
oculta los botones en el frontend, sino que también bloquea en el backend la
ejecución de la verificación y la descarga de certificado cuando está
deshabilitado — sin depender de que el frontend haga bien su parte.
"""

import pytest

from api.dependencies import sagrilaft_habilitado
from main import app as aplicacion_sagrilaft
from soporte.radicacion import radicar_formulario_juridico_con_documentos

pytestmark = pytest.mark.integration


def _con_flag_deshabilitado(habilitado: bool):
    aplicacion_sagrilaft.dependency_overrides[sagrilaft_habilitado] = lambda: habilitado


def _quitar_override_flag():
    aplicacion_sagrilaft.dependency_overrides.pop(sagrilaft_habilitado, None)


def test_disponibilidad_sagrilaft_refleja_el_flag(cliente_api):
    # El harness de integración corre con PROVEEDOR_LISTAS_CAUTELA=dummy.
    respuesta = cliente_api.get("/api/expedientes/sagrilaft/disponibilidad")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"habilitado": True}

    _con_flag_deshabilitado(False)
    try:
        respuesta = cliente_api.get("/api/expedientes/sagrilaft/disponibilidad")
    finally:
        _quitar_override_flag()
    assert respuesta.json() == {"habilitado": False}


def test_verificar_sagrilaft_rechaza_con_409_si_el_flag_esta_deshabilitado(cliente_api):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)

    _con_flag_deshabilitado(False)
    try:
        respuesta = cliente_api.post(
            f"/api/expedientes/{acceso['formulario_id']}/verificar-sagrilaft"
        )
    finally:
        _quitar_override_flag()

    assert respuesta.status_code == 409, respuesta.text
    assert "deshabilitad" in respuesta.json()["detail"].lower()


@pytest.mark.parametrize("numero, estado, reporte_id", [
    ("123456789", "APROBADO_SAGRILAFT", "dummy_limpio_123"),
    ("999123456", "RECHAZADO_SAGRILAFT", "dummy_hallazgo_456"),
    ("888123456", "RECHAZADO_SAGRILAFT", "dummy_hallazgo_456"),
    ("777123456", "RECHAZADO_SAGRILAFT", "dummy_hallazgo_456"),
])
def test_dummy_verifica_persiste_reporte_y_descarga_pdf(cliente_api, numero, estado, reporte_id):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    ruta = f"/api/expedientes/{acceso['formulario_id']}"
    detalle_antes = cliente_api.get(ruta).json()
    assert detalle_antes["sagrilaft_reporte_id"] is None

    respuesta = cliente_api.post(
        f"{ruta}/verificar-sagrilaft",
        json={"tipo_identificacion": "CC", "numero_identificacion": numero,
              "nombre_completo": "Contraparte de prueba"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == estado
    detalle = cliente_api.get(ruta)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["sagrilaft_reporte_id"] == reporte_id
    # La consulta guarda el reporte; no aprueba/rechaza el estado del expediente.
    assert detalle.json()["estado"] == detalle_antes["estado"]

    certificado = cliente_api.get(f"{ruta}/sagrilaft/pdf")
    assert certificado.status_code == 200, certificado.text
    assert certificado.headers["content-type"] == "application/pdf"
    assert "attachment;" in certificado.headers["content-disposition"]
    assert certificado.content.startswith(b"%PDF-")


def test_dummy_error_no_crea_reporte(cliente_api):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    ruta = f"/api/expedientes/{acceso['formulario_id']}"
    respuesta = cliente_api.post(f"{ruta}/verificar-sagrilaft", json={
        "tipo_identificacion": "CC", "numero_identificacion": "000123456",
        "nombre_completo": "Contraparte de prueba",
    })
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "ERROR_VERIFICACION"
    assert cliente_api.get(ruta).json()["sagrilaft_reporte_id"] is None
    certificado = cliente_api.get(f"{ruta}/sagrilaft/pdf")
    assert certificado.status_code == 404, certificado.text


def test_descargar_certificado_sagrilaft_rechaza_con_409_si_el_flag_esta_deshabilitado(
    cliente_api,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)

    _con_flag_deshabilitado(False)
    try:
        respuesta = cliente_api.get(
            f"/api/expedientes/{acceso['formulario_id']}/sagrilaft/pdf"
        )
    finally:
        _quitar_override_flag()

    assert respuesta.status_code == 409, respuesta.text
    assert "deshabilitad" in respuesta.json()["detail"].lower()
