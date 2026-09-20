"""
Verifica que la configuración del proveedor de listas de cautela
(PROVEEDOR_LISTAS_CAUTELA / SAGRILAFT_API_URL / SAGRILAFT_API_KEY) tenga una
única fuente de verdad (AppConfig.listas_cautela) y falle rápido si producción
quedaría corriendo en modo simulado ("dummy"). Staging puede usar dummy mientras
la API real no esté disponible.

Contexto: antes, `infrastructure/servicios_externos/sagrilaft/fabrica.py` leía
estas variables directamente con `os.getenv`, fuera de `load_config()` — un
despliegue sin las variables cableadas en la infraestructura caía en "dummy"
sin ningún error.
"""

import pytest

from infrastructure.config.configuracion import AppConfig, SagrilaftListasConfig, load_config
from infrastructure.servicios_externos.sagrilaft.fabrica import (
    PROVEEDOR_DESHABILITADO,
    PROVEEDOR_DUMMY,
    PROVEEDOR_SAGRILAFT,
    obtener_consultor_listas,
)
from infrastructure.servicios_externos.sagrilaft.dummy import ConsultorListasCautelaDummy
from infrastructure.servicios_externos.sagrilaft.real import ConsultorListasCautelaAPI
from infrastructure.servicios_externos.sagrilaft.deshabilitado import ConsultorListasCautelaDeshabilitado
from fastapi import HTTPException

from api.dependencies import exigir_sagrilaft_habilitado, sagrilaft_habilitado
from api.routers.expedientes import disponibilidad_sagrilaft
from api.schemas import DisponibilidadSagrilaft


def _preparar_env_base(monkeypatch, entorno: str) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("APP_ENV", entorno)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "bucket-de-prueba")
    monkeypatch.setenv("FRONTEND_URL", "https://forms.test")
    monkeypatch.setenv("PORTAL_INTERNO_URL", "https://portal.test")


# ─── obtener_consultor_listas: ahora recibe config por DI, sin os.getenv ─────

def test_obtener_consultor_listas_dummy_por_defecto():
    config = SagrilaftListasConfig(proveedor="dummy", api_url="", api_key="")
    assert isinstance(obtener_consultor_listas(config), ConsultorListasCautelaDummy)


def test_obtener_consultor_listas_deshabilitado():
    config = SagrilaftListasConfig(proveedor="deshabilitado", api_url="", api_key="")
    assert isinstance(obtener_consultor_listas(config), ConsultorListasCautelaDeshabilitado)


def test_obtener_consultor_listas_sagrilaft_usa_config_inyectada():
    config = SagrilaftListasConfig(
        proveedor="sagrilaft",
        api_url="https://api.tusdatos.co",
        api_key="usuario:clave",
    )
    consultor = obtener_consultor_listas(config)
    assert isinstance(consultor, ConsultorListasCautelaAPI)
    assert consultor._url_base == "https://api.tusdatos.co"


# ─── load_config(): fail-fast en producción/staging ──────────────────────────

def test_load_config_rechaza_dummy_en_produccion(monkeypatch):
    _preparar_env_base(monkeypatch, "production")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "dummy")
    with pytest.raises(RuntimeError, match="PROVEEDOR_LISTAS_CAUTELA"):
        load_config()


def test_load_config_permite_dummy_en_staging(monkeypatch):
    _preparar_env_base(monkeypatch, "staging")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "dummy")
    cfg = load_config()
    assert cfg.listas_cautela.proveedor == "dummy"


def test_load_config_rechaza_sagrilaft_sin_credenciales_en_staging(monkeypatch):
    _preparar_env_base(monkeypatch, "staging")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "sagrilaft")
    monkeypatch.delenv("SAGRILAFT_API_URL", raising=False)
    monkeypatch.delenv("SAGRILAFT_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SAGRILAFT_API_URL"):
        load_config()


def test_load_config_acepta_sagrilaft_configurado_en_produccion(monkeypatch):
    _preparar_env_base(monkeypatch, "production")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "sagrilaft")
    monkeypatch.setenv("SAGRILAFT_API_URL", "https://api.tusdatos.co")
    monkeypatch.setenv("SAGRILAFT_API_KEY", "usuario:clave")
    cfg = load_config()
    assert cfg.listas_cautela.proveedor == "sagrilaft"
    assert cfg.listas_cautela.configurado


def test_load_config_permite_dummy_en_development(monkeypatch):
    _preparar_env_base(monkeypatch, "development")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "dummy")
    cfg = load_config()
    assert cfg.listas_cautela.proveedor == "dummy"


# ─── sagrilaft_habilitado / exigir_sagrilaft_habilitado: mismo flag en todos
# lados ─────────────────────────────────────────────────────────────────────
#
# El frontend usa GET /api/expedientes/sagrilaft/disponibilidad para ocultar
# el botón "Verificar SAGRILAFT". Pero ocultar el botón no alcanza: alguien
# podría llamar el endpoint directamente (Postman, script) mientras el
# proveedor está deshabilitado. `exigir_sagrilaft_habilitado` corta esa
# petición en la capa HTTP (409) antes de llegar al servicio, para que el
# Null Object no "apruebe" en silencio una verificación que nunca ocurrió.
# Se prueba llamando las funciones directamente (sin resolver los `Depends`),
# igual que se hace arriba con `obtener_consultor_listas`.

def _config_con_proveedor(proveedor: str) -> AppConfig:
    return AppConfig(listas_cautela=SagrilaftListasConfig(proveedor=proveedor, api_url="", api_key=""))


def test_sagrilaft_habilitado_es_false_solo_para_deshabilitado():
    assert sagrilaft_habilitado(_config_con_proveedor(PROVEEDOR_DESHABILITADO)) is False
    assert sagrilaft_habilitado(_config_con_proveedor(PROVEEDOR_DUMMY)) is True
    assert sagrilaft_habilitado(_config_con_proveedor(PROVEEDOR_SAGRILAFT)) is True


def test_exigir_sagrilaft_habilitado_rechaza_con_409_si_esta_deshabilitado():
    with pytest.raises(HTTPException) as excinfo:
        exigir_sagrilaft_habilitado(habilitado=False)
    assert excinfo.value.status_code == 409
    assert "deshabilitad" in excinfo.value.detail.lower()


def test_exigir_sagrilaft_habilitado_no_rechaza_si_esta_habilitado():
    assert exigir_sagrilaft_habilitado(habilitado=True) is None


def test_disponibilidad_sagrilaft_reporta_deshabilitado():
    resultado = disponibilidad_sagrilaft(usuario=None, habilitado=False)
    assert resultado == DisponibilidadSagrilaft(habilitado=False)


def test_disponibilidad_sagrilaft_reporta_habilitado():
    resultado = disponibilidad_sagrilaft(usuario=None, habilitado=True)
    assert resultado == DisponibilidadSagrilaft(habilitado=True)
