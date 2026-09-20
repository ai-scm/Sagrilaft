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


def test_verificar_sagrilaft_funciona_si_el_flag_esta_habilitado(cliente_api):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/verificar-sagrilaft"
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] in {"APROBADO_SAGRILAFT", "RECHAZADO_SAGRILAFT"}


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
