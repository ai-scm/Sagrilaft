"""
Verifica que APP_ENV tenga una única fuente de verdad (entorno_actual()).

Contexto: antes, `api/middleware/autenticacion.py` leía APP_ENV por su cuenta
con `os.getenv("APP_ENV", "production")`, mientras `infrastructure/configuracion.py`
exigía `os.environ["APP_ENV"]` sin default. Ambas lecturas podían divergir.
Ahora las dos pasan por `entorno_actual()`.
"""

from pathlib import Path

import pytest

from infrastructure.config.configuracion import entorno_actual


def test_entorno_actual_falla_si_no_esta_definida(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError, match="APP_ENV"):
        entorno_actual()


def test_entorno_actual_normaliza_a_minusculas(monkeypatch):
    monkeypatch.setenv("APP_ENV", "PRODUCTION")
    assert entorno_actual() == "production"


def test_autenticacion_usa_entorno_actual_no_su_propio_default():
    """El módulo de autenticación no debe tener ningún default propio para APP_ENV.

    Se inspecciona el código fuente en vez de importar el módulo: importarlo
    ejecuta `entorno_actual()` a nivel de módulo (falla sin APP_ENV) y puede
    disparar `sys.exit(1)` según PORTAL_AUTH_DISABLED — efectos secundarios
    que no queremos en este test.
    """
    ruta = Path(__file__).resolve().parents[2] / "backend" / "api" / "middleware" / "autenticacion.py"
    codigo_fuente = ruta.read_text(encoding="utf-8")
    assert 'os.getenv("APP_ENV"' not in codigo_fuente
    assert "entorno_actual()" in codigo_fuente
