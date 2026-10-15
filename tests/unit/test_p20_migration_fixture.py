import importlib.util
import builtins
import os
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "backend/scripts/p20_fail_before_ddl.py"


def test_fixture_exits_before_ddl_with_only_synthetic_marker(monkeypatch, capsys):
    monkeypatch.setenv("P20_LAB_RUN_ID", "p20-012345abcdef")
    spec = importlib.util.spec_from_file_location("p20_fixture", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 42
    output = capsys.readouterr().out
    assert '"stage": "before_ddl"' in output
    assert '"databaseTouched": false' in output
    assert '"runId": "p20-012345abcdef"' in output


def test_fixture_refuses_non_p20_run_id(monkeypatch, capsys):
    monkeypatch.setenv("P20_LAB_RUN_ID", "staging")
    spec = importlib.util.spec_from_file_location("p20_fixture_invalid", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 64
    assert "invalid lab run id" in capsys.readouterr().err


def test_fixture_cannot_import_migrations_connect_or_spawn_commands(monkeypatch, capsys):
    """Exercise the actual fixture with migration mode inherited and traps armed."""
    monkeypatch.setenv("P20_LAB_RUN_ID", "p20-012345abcdef")
    monkeypatch.setenv("RUN_MODE", "migrate")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"alembic", "psycopg", "psycopg2", "sqlalchemy"}:
            raise AssertionError("The inert fixture must not import DB or migration code")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("The inert fixture must not open sockets or spawn commands")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    spec = importlib.util.spec_from_file_location("p20_fixture_guarded", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 42
    assert '"databaseTouched": false' in capsys.readouterr().out
