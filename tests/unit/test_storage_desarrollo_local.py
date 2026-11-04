from pathlib import Path

import pytest

from infrastructure.config.configuracion import load_config
from infrastructure.storage.backend import LocalStorage, crear_storage


@pytest.fixture
def entorno_desarrollo(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setenv("PORTAL_INTERNO_URL", "http://localhost:5174")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.delenv("S3_BUCKET", raising=False)


def test_desarrollo_carga_config_sin_s3_bucket(entorno_desarrollo):
    cfg = load_config()
    assert cfg.storage_backend == "local"
    assert cfg.s3.bucket == ""


def test_desarrollo_usa_disco_local_sin_bucket(entorno_desarrollo, tmp_path: Path):
    cfg = load_config()
    storage = crear_storage(
        upload_dir=tmp_path,
        backend=cfg.storage_backend,
        s3_bucket=cfg.s3.bucket,
        s3_region=cfg.s3.region,
    )
    assert isinstance(storage, LocalStorage)
