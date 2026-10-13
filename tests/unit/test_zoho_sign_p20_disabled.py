from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.dependencies import exigir_zoho_sign_habilitado
from domain.excepciones import ZohoSignDeshabilitadoError
from infrastructure.config.configuracion import ZohoSignConfig
from infrastructure.zoho_sign.zoho_sign_disabled import ZohoSignDisabledService
from api.routers.expedientes import enrutador as router_expedientes
from api.routers.webhooks import enrutador as router_webhooks


def test_p20_can_disable_zoho_without_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("P20_RUN_ID", "p20-9c67b6ea6842")
    monkeypatch.setenv("ZOHO_SIGN_ENABLED", "false")
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)

    ZohoSignConfig().validar(entorno="staging")


@pytest.mark.parametrize(
    ("app_env", "run_id"),
    [
        ("staging", ""),
        ("staging", "p20-not-a-run-id"),
        ("production", "p20-9c67b6ea6842"),
    ],
)
def test_zoho_disabled_is_rejected_outside_p20(monkeypatch, app_env, run_id):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("P20_RUN_ID", run_id)
    monkeypatch.setenv("ZOHO_SIGN_ENABLED", "false")

    with pytest.raises(RuntimeError, match="solo se permite en un laboratorio P20"):
        ZohoSignConfig().validar(entorno=app_env)


def test_zoho_enabled_remains_the_default_and_still_requires_credentials(monkeypatch):
    monkeypatch.delenv("ZOHO_SIGN_ENABLED", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_REDIRECT_URI", raising=False)

    config = ZohoSignConfig()
    assert config.habilitado is True
    with pytest.raises(RuntimeError, match="ZOHO_CLIENT_ID"):
        config.validar(entorno="staging")


def test_invalid_zoho_enabled_value_fails_closed(monkeypatch):
    monkeypatch.setenv("ZOHO_SIGN_ENABLED", "disabled")
    with pytest.raises(RuntimeError, match="ZOHO_SIGN_ENABLED debe ser"):
        ZohoSignConfig()


def test_disabled_provider_rejects_every_operation_without_network(monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Zoho HTTP call must not be attempted")

    monkeypatch.setattr("infrastructure.zoho_sign.zoho_sign_service.httpx.request", forbidden_network)
    service = ZohoSignDisabledService()

    operations = [
        lambda: service.crear_solicitud_firma_multiple([], "doc", "test@example.invalid", "Tester"),
        lambda: service.descargar_documento_firmado("request-id", "/tmp/unused.pdf"),
        lambda: service.cancelar_solicitud_firma("request-id"),
        lambda: service.obtener_estado_solicitud("request-id"),
    ]
    for operation in operations:
        with pytest.raises(ZohoSignDeshabilitadoError):
            operation()


def test_signature_route_guard_blocks_when_zoho_is_disabled():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(zoho_sign=SimpleNamespace(habilitado=False)),
            ),
        ),
    )

    with pytest.raises(HTTPException, match="La firma electrónica está deshabilitada"):
        exigir_zoho_sign_habilitado(request)


def test_signature_route_guard_allows_when_zoho_is_enabled():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(zoho_sign=SimpleNamespace(habilitado=True)),
            ),
        ),
    )

    assert exigir_zoho_sign_habilitado(request) is None


def test_all_zoho_routes_have_the_early_disable_guard():
    protected_paths = {
        ("/api/expedientes/{formulario_id}/enviar-a-firma", "POST"),
        ("/api/expedientes/{formulario_id}/verificar-firma", "POST"),
        ("/api/expedientes/{formulario_id}/cancelar-firma", "POST"),
        ("/api/webhooks/zoho-sign", "POST"),
    }
    routes = [*router_expedientes.routes, *router_webhooks.routes]
    for path, method in protected_paths:
        route = next(route for route in routes if route.path == path and method in route.methods)
        assert any(dependency.dependency is exigir_zoho_sign_habilitado for dependency in route.dependencies)
