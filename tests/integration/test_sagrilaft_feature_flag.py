"""Transición F3: las rutas retiradas no modifican el expediente ni consultan proveedores."""
import pytest
from api.dependencies import sagrilaft_habilitado
from main import app as aplicacion_sagrilaft
from soporte.radicacion import radicar_formulario_juridico_con_documentos

pytestmark = pytest.mark.integration


def test_disponibilidad_heredada_no_habilita_rutas_retiradas(cliente_api):
    respuesta = cliente_api.get("/api/expedientes/sagrilaft/disponibilidad")
    assert respuesta.status_code == 200
    assert "habilitado" in respuesta.json()


@pytest.mark.parametrize("habilitado", [True, False])
@pytest.mark.parametrize("operacion", ["consulta", "pdf", "independiente"])
def test_rutas_anteriores_exigen_transicion_sin_modificar_expediente(cliente_api, habilitado, operacion):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    ruta = f"/api/expedientes/{acceso['formulario_id']}"
    anterior = cliente_api.get(ruta).json()
    aplicacion_sagrilaft.dependency_overrides[sagrilaft_habilitado] = lambda: habilitado
    try:
        if operacion == "consulta":
            respuesta = cliente_api.post(f"{ruta}/verificar-sagrilaft", json={"numero_identificacion": "999123456"})
        elif operacion == "pdf":
            respuesta = cliente_api.get(f"{ruta}/sagrilaft/pdf")
        else:
            respuesta = cliente_api.post("/api/listas-cautela/buscar", json={"nombre": "Persona ficticia"})
        assert respuesta.status_code == 410, respuesta.text
        posterior = cliente_api.get(ruta).json()
        assert posterior["estado"] == anterior["estado"]
        assert posterior["sagrilaft_reporte_id"] == anterior["sagrilaft_reporte_id"]
    finally:
        aplicacion_sagrilaft.dependency_overrides.pop(sagrilaft_habilitado, None)
