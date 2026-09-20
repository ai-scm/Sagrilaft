import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


pytestmark = pytest.mark.integration

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
BACKEND_DIR = RAIZ_PROYECTO / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _config_alembic() -> Config:
    return Config(str(ALEMBIC_INI))


def _url_admin_postgres() -> str:
    url = os.getenv("TEST_POSTGRES_ADMIN_URL") or os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip(
            "Defina TEST_POSTGRES_ADMIN_URL para validar migraciones contra PostgreSQL real."
        )

    parsed = make_url(url)
    maintenance_db = os.getenv("TEST_POSTGRES_MAINTENANCE_DB", "postgres")
    return parsed.set(database=maintenance_db).render_as_string(hide_password=False)


def _crear_base_temporal(admin_url: str) -> tuple[str, str]:
    nombre_bd = f"sagrilaft_alembic_test_{uuid.uuid4().hex}"
    temp_url = make_url(admin_url).set(database=nombre_bd)
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conexion:
        conexion.execute(text(f'CREATE DATABASE "{nombre_bd}"'))

    engine.dispose()
    return nombre_bd, temp_url.render_as_string(hide_password=False)


def _eliminar_base_temporal(admin_url: str, nombre_bd: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conexion:
        conexion.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :nombre_bd AND pid <> pg_backend_pid()
                """
            ),
            {"nombre_bd": nombre_bd},
        )
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre_bd}"'))
    engine.dispose()


def _columnas(inspector, tabla: str) -> dict[str, dict]:
    return {columna["name"]: columna for columna in inspector.get_columns(tabla)}


def test_alembic_tiene_un_solo_head():
    script = ScriptDirectory.from_config(_config_alembic())

    assert script.get_heads() == [script.get_current_head()]


def test_alembic_upgrade_head_crea_esquema_postgresql(monkeypatch):
    admin_url = _url_admin_postgres()
    nombre_bd, database_url = _crear_base_temporal(admin_url)

    try:
        monkeypatch.setenv("DATABASE_URL", database_url)
        command.upgrade(_config_alembic(), "head")

        engine = create_engine(database_url)
        inspector = inspect(engine)
        tablas = set(inspector.get_table_names())

        assert {
            "formularios",
            "accesos_manuales",
            "documentos_adjuntos",
            "eventos_formulario",
            "formulario_alertas_inconsistencia",
            "alembic_version",
        }.issubset(tablas)

        with engine.connect() as conexion:
            version = conexion.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            trigger = conexion.execute(
                text(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE tgname = 'tg_audit_estado'
                    """
                )
            ).scalar_one_or_none()

        assert version == ScriptDirectory.from_config(_config_alembic()).get_current_head()
        assert trigger == "tg_audit_estado"

        columnas_formularios = _columnas(inspector, "formularios")
        assert "numero_correccion" in columnas_formularios
        assert "zoho_request_id" in columnas_formularios
        assert "ruta_documento_firmado" in columnas_formularios
        assert "sagrilaft_reporte_id" in columnas_formularios

        columnas_accesos = _columnas(inspector, "accesos_manuales")
        assert columnas_accesos["correo_destinatario"]["nullable"] is False
        assert "ultimo_envio_correo" in columnas_accesos

        columnas_documentos = _columnas(inspector, "documentos_adjuntos")
        assert "version_numero" in columnas_documentos
        assert "version_anterior_id" in columnas_documentos
        assert "hash_sha256" in columnas_documentos
        assert "snapshot_datos" in columnas_documentos

        engine.dispose()
    finally:
        _eliminar_base_temporal(admin_url, nombre_bd)
