"""La selección local por archivos no habilita otros entornos ni inventa fuentes."""
from uuid import uuid4

import pytest

from domain.listas.puertos import ListasNoDisponibles
from infrastructure.listas.configuracion_archivos import ConfiguracionArchivosLocal


@pytest.fixture
def configuracion_local(monkeypatch):
    politica = uuid4()
    monkeypatch.setenv("LISTAS_ARCHIVOS_LOCAL_HABILITADA", "true")
    monkeypatch.setenv("LISTAS_ARCHIVOS_FUENTES", "ofac_sdn,lista_propia")
    monkeypatch.setenv("LISTAS_ARCHIVOS_POLITICA_ID", str(politica))
    return politica


@pytest.mark.parametrize("entorno", ["development", "test"])
def test_f64_fuentes_y_politica_explicitas(configuracion_local, entorno):
    configuracion = ConfiguracionArchivosLocal.cargar(entorno)
    assert configuracion.fuentes == ("ofac_sdn", "lista_propia")
    assert configuracion.politica_id == configuracion_local


@pytest.mark.parametrize("entorno", ["staging", "production"])
def test_f64_no_habilita_entornos_remotos(configuracion_local, entorno):
    with pytest.raises(ListasNoDisponibles):
        ConfiguracionArchivosLocal.cargar(entorno)


@pytest.mark.parametrize("variable,valor", [
    ("LISTAS_ARCHIVOS_LOCAL_HABILITADA", "false"),
    ("LISTAS_ARCHIVOS_FUENTES", ""),
    ("LISTAS_ARCHIVOS_FUENTES", "ofac_sdn,ofac_sdn"),
    ("LISTAS_ARCHIVOS_POLITICA_ID", ""),
    ("LISTAS_ARCHIVOS_POLITICA_ID", "no-es-uuid"),
])
def test_f64_configuracion_incompleta_no_se_sustituye(configuracion_local, monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ListasNoDisponibles):
        ConfiguracionArchivosLocal.cargar("development")


@pytest.mark.parametrize("proveedor", [None, ""])
def test_proveedor_antiguo_vacio_equivale_a_ausente(monkeypatch, proveedor):
    from infrastructure.config.configuracion import SagrilaftListasConfig
    monkeypatch.setenv("LISTAS_IMPLEMENTACION", "archivos")
    if proveedor is None:
        monkeypatch.delenv("PROVEEDOR_LISTAS_CAUTELA", raising=False)
    else:
        monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", proveedor)
    assert SagrilaftListasConfig().implementacion == "archivos"


def test_proveedor_antiguo_contradictorio_sigue_rechazado(monkeypatch):
    from infrastructure.config.configuracion import SagrilaftListasConfig
    monkeypatch.setenv("LISTAS_IMPLEMENTACION", "archivos")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "deshabilitado")
    with pytest.raises(RuntimeError, match="contradictorios"):
        SagrilaftListasConfig()


def test_proveedor_antiguo_vacio_sin_implementacion_explicita_sigue_rechazado(monkeypatch):
    from infrastructure.config.configuracion import SagrilaftListasConfig
    monkeypatch.delenv("LISTAS_IMPLEMENTACION", raising=False)
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "")
    with pytest.raises(RuntimeError):
        SagrilaftListasConfig()
