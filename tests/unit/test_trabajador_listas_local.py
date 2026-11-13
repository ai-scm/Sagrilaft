import pytest
from infrastructure.listas.trabajador_local import validar_destino


@pytest.mark.parametrize("entorno,host,base", [
    ("production", "postgres", "local"),
    ("staging", "postgres", "local"),
    ("development", "servidor-remoto", "local"),
    ("development", "postgres", "otra"),
])
def test_rechaza_destino_fuera_del_compose(monkeypatch, entorno, host, base):
    monkeypatch.setenv("APP_ENV", entorno)
    monkeypatch.setenv("DATABASE_URL", f"postgresql://usuario@{host}/{base}")
    monkeypatch.setenv("LISTAS_BASE_LOCAL", "local")
    with pytest.raises(RuntimeError):
        validar_destino()


def test_admite_base_local_explicita(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario@postgres/local")
    monkeypatch.setenv("LISTAS_BASE_LOCAL", "local")
    assert validar_destino() == "development"
