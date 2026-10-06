import pytest
import os
from pathlib import Path
import subprocess
from sqlalchemy import create_engine, text

from infrastructure.persistencia.migration_guard import (
    migration_lock, require_single_head, verify_revision,
)


@pytest.mark.parametrize("heads", [[], ["one", "two"]])
def test_requires_exactly_one_image_head(heads):
    with pytest.raises(RuntimeError, match="exactamente un head"):
        require_single_head(heads)


def test_single_image_head():
    assert require_single_head(["expected"]) == "expected"


def test_revision_verification_rejects_empty_wrong_and_multiple_heads():
    with create_engine("sqlite://").connect() as connection:
        with pytest.raises(RuntimeError, match="inesperada"):
            verify_revision(connection, "expected")
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('old')"))
        with pytest.raises(RuntimeError, match="inesperada"):
            verify_revision(connection, "expected")
        connection.execute(text("UPDATE alembic_version SET version_num='expected'"))
        assert verify_revision(connection, "expected") == ("expected",)
        connection.execute(text("INSERT INTO alembic_version VALUES ('other')"))
        with pytest.raises(RuntimeError, match="inesperada"):
            verify_revision(connection, "expected")


def test_sqlite_does_not_execute_postgres_lock_or_commit_callers_transaction():
    with create_engine("sqlite://").connect() as connection:
        with connection.begin():
            with migration_lock(connection):
                assert connection.in_transaction()


@pytest.mark.parametrize("mode,exit_code", [("server", 0), ("migrate", 0), ("migrate", 7)])
def test_entrypoint_only_verifies_migration_mode_and_propagates_failure(tmp_path, mode, exit_code):
    # Simula conectividad y ejecutables, sin base ni servidor HTTP reales.
    for name, body in {
        "python": "cat >/dev/null\nexit 0",
        "alembic": f'echo "verify=$MIGRATION_VERIFY_HEAD args=$*"\nexit {exit_code}',
        "uvicorn": 'echo "SERVER_STARTED"',
    }.items():
        executable = tmp_path / name
        executable.write_text("#!/bin/sh\n" + body + "\n")
        executable.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "APP_ENV": "development", "RUN_MODE": mode}
    result = subprocess.run(["sh", str(Path(__file__).resolve().parents[2] / "backend/entrypoint.sh")],
                            env=env, capture_output=True, text=True)
    assert result.returncode == exit_code
    if mode == "server":
        assert "SERVER_STARTED" in result.stdout and "verify=" not in result.stdout
    else:
        assert "verify=1 args=upgrade head" in result.stdout
        assert "SERVER_STARTED" not in result.stdout
        assert ("Migraciones completadas" in result.stdout) == (exit_code == 0)
