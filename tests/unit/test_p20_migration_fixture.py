import importlib.util
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
