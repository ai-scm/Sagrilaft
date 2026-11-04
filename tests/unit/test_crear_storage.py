from pathlib import Path

import pytest

from infrastructure.config.configuracion import load_config
from infrastructure.storage.backend import LocalStorage, S3Storage, crear_storage


def test_local_devuelve_local_storage(tmp_path: Path):
    storage = crear_storage(upload_dir=tmp_path, backend="local", s3_bucket="", s3_region="us-east-1")
    assert isinstance(storage, LocalStorage)


def test_s3_con_bucket_devuelve_s3_storage(tmp_path: Path):
    storage = crear_storage(upload_dir=tmp_path, backend="s3", s3_bucket="mi-bucket", s3_region="us-east-1")
    assert isinstance(storage, S3Storage)


def test_s3_sin_bucket_lanza_error_claro(tmp_path: Path):
    with pytest.raises(RuntimeError, match="requiere S3_BUCKET"):
        crear_storage(upload_dir=tmp_path, backend="s3", s3_bucket="", s3_region="us-east-1")


def test_s3_con_bucket_solo_espacios_lanza_error(tmp_path: Path):
    with pytest.raises(RuntimeError, match="requiere S3_BUCKET"):
        crear_storage(upload_dir=tmp_path, backend="s3", s3_bucket="   ", s3_region="us-east-1")


def test_s3_en_mayusculas_no_cae_a_local(tmp_path: Path):
    storage = crear_storage(upload_dir=tmp_path, backend="S3", s3_bucket="mi-bucket", s3_region="us-east-1")
    assert isinstance(storage, S3Storage)


def test_backend_desconocido_lanza_error(tmp_path: Path):
    with pytest.raises(RuntimeError, match="no es válido"):
        crear_storage(upload_dir=tmp_path, backend="gcs", s3_bucket="", s3_region="us-east-1")


@pytest.fixture
def entorno_base(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FRONTEND_URL", "https://forms.test")
    monkeypatch.setenv("PORTAL_INTERNO_URL", "https://portal.test")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "deshabilitado")
    monkeypatch.delenv("S3_BUCKET", raising=False)


@pytest.mark.parametrize("entorno", ["staging", "production"])
def test_produccion_s3_sin_bucket_falla_en_config(monkeypatch, entorno_base, entorno):
    monkeypatch.setenv("APP_ENV", entorno)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    with pytest.raises(RuntimeError, match="S3_BUCKET es obligatorio"):
        load_config()


@pytest.mark.parametrize("entorno", ["staging", "production"])
def test_produccion_s3_con_bucket_carga_config(monkeypatch, entorno_base, entorno, tmp_path):
    monkeypatch.setenv("APP_ENV", entorno)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "bucket-cdk-real")
    cfg = load_config()
    storage = crear_storage(
        upload_dir=tmp_path,
        backend=cfg.storage_backend,
        s3_bucket=cfg.s3.bucket,
        s3_region=cfg.s3.region,
    )
    assert isinstance(storage, S3Storage)


def test_desarrollo_s3_sin_bucket_falla_al_crear_storage(monkeypatch, entorno_base, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    cfg = load_config()
    with pytest.raises(RuntimeError, match="requiere S3_BUCKET"):
        crear_storage(
            upload_dir=tmp_path,
            backend=cfg.storage_backend,
            s3_bucket=cfg.s3.bucket,
            s3_region=cfg.s3.region,
        )


def test_desarrollo_local_no_requiere_s3(monkeypatch, entorno_base, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    cfg = load_config()
    storage = crear_storage(
        upload_dir=tmp_path,
        backend=cfg.storage_backend,
        s3_bucket=cfg.s3.bucket,
        s3_region=cfg.s3.region,
    )
    assert isinstance(storage, LocalStorage)
