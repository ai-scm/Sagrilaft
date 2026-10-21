"""Smoke de solo lectura probado sin red: un cliente falso sustituye a http.client."""
import http.client
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "despliegue"))
import smoke_readonly as smoke

SHA = "a" * 40
FORMS = "forms.example.com"
PORTAL = "portal.example.com"
KEYCLOAK = "login.example.com"
HSTS = {"Strict-Transport-Security": "max-age=31536000"}
ARGS = ["--environment", "prod", "--sha", SHA, "--forms-domain", FORMS,
        "--portal-domain", PORTAL, "--keycloak-domain", KEYCLOAK]


def healthy_body(sha=SHA, database="ok", status="healthy"):
    return json.dumps({"status": status, "commit": sha, "dependencies": {"database": database}}).encode()


def oidc_body(domain=KEYCLOAK, realm="sagrilaft"):
    return json.dumps({"issuer": f"https://{domain}/realms/{realm}"}).encode()


def good_routes():
    routes = {}
    for domain in (FORMS, PORTAL, KEYCLOAK):
        routes[("http", domain, "/")] = smoke.Response(301, {"Location": f"https://{domain}/"}, b"")
        routes[("https", domain, "/")] = smoke.Response(200, HSTS, b"<html></html>")
    routes[("https", KEYCLOAK, "/")] = smoke.Response(302, HSTS, b"")
    for domain in (FORMS, PORTAL):
        routes[("https", domain, "/health")] = smoke.Response(200, {}, healthy_body())
    routes[("https", KEYCLOAK, "/realms/sagrilaft/.well-known/openid-configuration")] = smoke.Response(200, {}, oidc_body())
    return routes


class FakeClient:
    """Registra cada petición; lanza una excepción real si la ruta falla o no existe."""

    def __init__(self, routes, failures=None):
        self.routes = routes
        self.failures = failures or {}
        self.calls = []
        self.methods_used = set()

    def request(self, method, scheme, host, path):
        if method not in smoke.READ_ONLY_METHODS:
            raise ValueError("método no permitido")
        self.calls.append((method, scheme, host, path))
        self.methods_used.add(method)
        key = (scheme, host, path)
        if key in self.failures:
            raise self.failures[key]
        return self.routes[key]


def config(**overrides):
    cfg = {"environment": "prod", "sha": SHA, "forms_domain": FORMS, "portal_domain": PORTAL,
           "keycloak_domain": KEYCLOAK, "realm": "sagrilaft", "timeout": 30, "interval": 5}
    cfg.update(overrides)
    return cfg


def failed(summary):
    return {r["check"] for r in summary["results"] if not r["ok"]}


class Timeline:
    """Reloj falso que avanza solo con sleep: los casos que fallan alcanzan el plazo sin esperar."""

    def __init__(self):
        self.now = 0

    def sleep(self, seconds):
        self.now += seconds

    def clock(self):
        return self.now


def run(routes, **overrides):
    timeline = Timeline()
    return smoke.smoke(FakeClient(routes), config(**overrides), sleep=timeline.sleep, clock=timeline.clock)


def test_all_checks_pass_with_a_healthy_release():
    client = FakeClient(good_routes())
    summary = smoke.smoke(client, config(), sleep=lambda s: None, clock=lambda: 0)
    assert summary["passed"] is True and failed(summary) == set()
    assert summary["readonly"] is True and summary["methods_used"] == ["GET"]
    assert len(summary["results"]) == 12  # 3 dominios x 3 + 2 health + 1 OIDC
    assert {c[0] for c in client.calls} == {"GET"}


def test_cli_exit_code_and_json_output(capsys):
    assert smoke.main(ARGS, client=FakeClient(good_routes()), sleep=lambda s: None, clock=lambda: 0) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True and out["sha"] == SHA and out["environment"] == "prod"
    routes = good_routes()
    routes[("https", PORTAL, "/health")] = smoke.Response(200, {}, healthy_body(sha="b" * 40))
    timeline = Timeline()
    assert smoke.main(ARGS, client=FakeClient(routes), sleep=timeline.sleep, clock=timeline.clock) == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_client_rejects_every_non_read_method():
    client = smoke.HttpClient()
    for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        with pytest.raises(ValueError):
            client.request(method, "https", FORMS, "/")
    assert client.methods_used == set()


def test_only_get_requests_and_no_bodies_or_state_changing_paths():
    client = FakeClient(good_routes())
    smoke.smoke(client, config(), sleep=lambda s: None, clock=lambda: 0)
    assert {c[0] for c in client.calls} == {"GET"}
    assert {c[3] for c in client.calls} == {"/", "/health", "/realms/sagrilaft/.well-known/openid-configuration"}
    assert not any(token in c[3] for c in client.calls for token in ("/api/", "login", "token", "acceso"))


@pytest.mark.parametrize("domain", [FORMS, PORTAL, KEYCLOAK])
def test_missing_https_redirect_fails(domain):
    routes = good_routes()
    routes[("http", domain, "/")] = smoke.Response(200, {}, b"")
    assert any("redirección" in c for c in failed(run(routes)))


def test_redirect_to_another_host_fails():
    routes = good_routes()
    routes[("http", FORMS, "/")] = smoke.Response(301, {"Location": "https://evil.example.net/"}, b"")
    assert failed(run(routes)) == {"formulario: redirección HTTP→HTTPS"}


@pytest.mark.parametrize("header", [{}, {"Strict-Transport-Security": "max-age=300"},
                                    {"Strict-Transport-Security": "includeSubDomains"}])
def test_hsts_must_be_present_and_long_enough(header):
    routes = good_routes()
    routes[("https", PORTAL, "/")] = smoke.Response(200, header, b"")
    assert failed(run(routes)) == {f"portal: HSTS (max-age >= {smoke.MIN_HSTS_SECONDS})"}


def test_hsts_longer_than_minimum_is_accepted():
    routes = good_routes()
    routes[("https", PORTAL, "/")] = smoke.Response(200, {"strict-transport-security": "max-age=63072000; includeSubDomains"}, b"")
    assert run(routes)["passed"] is True


def test_application_domains_require_exactly_200_but_keycloak_may_redirect():
    routes = good_routes()
    routes[("https", FORMS, "/")] = smoke.Response(302, HSTS, b"")
    assert failed(run(routes)) == {"formulario: respuesta HTTPS"}
    routes[("https", FORMS, "/")] = smoke.Response(200, HSTS, b"")
    routes[("https", KEYCLOAK, "/")] = smoke.Response(500, HSTS, b"")
    assert failed(run(routes)) == {"keycloak: respuesta HTTPS"}


@pytest.mark.parametrize("body,status,expected", [
    (healthy_body(sha="b" * 40), 200, "commit no coincide"),
    (healthy_body(database="error"), 200, "base de datos"),
    (healthy_body(status="degraded"), 200, "status distinto"),
    (b"no es json", 200, "sin JSON válido"),
    (b"[1, 2]", 200, "sin JSON válido"),
    (healthy_body(), 503, "sin JSON válido"),
])
def test_health_requires_candidate_commit_and_database(body, status, expected):
    routes = good_routes()
    routes[("https", FORMS, "/health")] = smoke.Response(status, {}, body)
    summary = run(routes)
    assert failed(summary) == {"formulario: /health"}
    assert expected in next(r["detail"] for r in summary["results"] if r["check"] == "formulario: /health")


def test_health_without_dependencies_block_fails():
    routes = good_routes()
    routes[("https", PORTAL, "/health")] = smoke.Response(200, {}, json.dumps({"status": "healthy", "commit": SHA}).encode())
    assert failed(run(routes)) == {"portal: /health"}


@pytest.mark.parametrize("body,status", [(oidc_body(domain="other.example.com"), 200),
                                         (oidc_body(realm="otro"), 200), (b"{}", 200), (oidc_body(), 404)])
def test_keycloak_oidc_issuer_must_match_domain_and_realm(body, status):
    routes = good_routes()
    routes[("https", KEYCLOAK, "/realms/sagrilaft/.well-known/openid-configuration")] = smoke.Response(status, {}, body)
    assert failed(run(routes)) == {"keycloak: documento OIDC del realm"}


@pytest.mark.parametrize("error", [ConnectionRefusedError(), TimeoutError(), http.client.RemoteDisconnected("x")])
def test_connection_errors_fail_without_crashing(error):
    client = FakeClient(good_routes(), failures={("https", FORMS, "/health"): error})
    timeline = Timeline()
    summary = smoke.smoke(client, config(), sleep=timeline.sleep, clock=timeline.clock)
    assert failed(summary) == {"formulario: /health"}
    assert "error de conexión" in next(r["detail"] for r in summary["results"] if r["check"] == "formulario: /health")


def test_retries_until_services_are_ready_then_passes():
    now = {"t": 0}
    attempts = {"n": 0}
    base = good_routes()

    class Warming(FakeClient):
        def request(self, method, scheme, host, path):
            if path == "/health" and attempts["n"] < 3:
                raise ConnectionRefusedError()
            return super().request(method, scheme, host, path)

    client = Warming(base)

    def sleep(seconds):
        now["t"] += seconds
        attempts["n"] += 1

    summary = smoke.smoke(client, config(timeout=60, interval=5), sleep=sleep, clock=lambda: now["t"])
    assert summary["passed"] is True and summary["attempts"] == 4


def test_gives_up_when_the_deadline_expires():
    now = {"t": 0}
    routes = good_routes()
    routes[("https", PORTAL, "/health")] = smoke.Response(200, {}, healthy_body(sha="b" * 40))

    def sleep(seconds):
        now["t"] += seconds

    summary = smoke.smoke(FakeClient(routes), config(timeout=20, interval=5), sleep=sleep, clock=lambda: now["t"])
    assert summary["passed"] is False and 2 <= summary["attempts"] <= 5
    assert now["t"] <= 20


@pytest.mark.parametrize("bad", [["--sha", "abc"], ["--sha", "A" * 40], ["--sha", "a" * 39],
                                 ["--forms-domain", "https://forms.example.com"],
                                 ["--forms-domain", "forms.example.com/path"],
                                 ["--portal-domain", "user@portal.example.com"],
                                 ["--keycloak-domain", "LOGIN.example.com"],
                                 ["--keycloak-domain", "localhost"],
                                 ["--realm", "../admin"], ["--timeout", "0"], ["--timeout", "9999"],
                                 ["--interval", "0"], ["--environment", "dev"],
                                 ["--portal-domain", FORMS]])
def test_invalid_arguments_exit_with_usage_error(bad):
    options = dict(zip(ARGS[::2], ARGS[1::2]))
    options[bad[0]] = bad[1]
    argv = [item for pair in options.items() for item in pair]
    with pytest.raises(SystemExit) as exc:
        smoke.parse_args(argv)
    assert exc.value.code == 2


def test_valid_arguments_are_accepted():
    args = smoke.parse_args(ARGS + ["--timeout", "300", "--interval", "15", "--realm", "otro-realm"])
    assert (args.environment, args.sha, args.timeout, args.interval, args.realm) == ("prod", SHA, 300, 15, "otro-realm")


def test_skip_hsts_option_no_longer_exists():
    with pytest.raises(SystemExit):
        smoke.parse_args(ARGS + ["--skip-hsts"])


def test_evidence_file_is_private_and_never_overwritten(tmp_path, capsys):
    target = tmp_path / "smoke.json"
    assert smoke.main(ARGS + ["--evidence-file", str(target)], client=FakeClient(good_routes()),
                      sleep=lambda s: None, clock=lambda: 0) == 0
    capsys.readouterr()
    assert json.loads(target.read_text())["passed"] is True
    assert oct(target.stat().st_mode & 0o777) == "0o600"
    with pytest.raises(FileExistsError):
        smoke.main(ARGS + ["--evidence-file", str(target)], client=FakeClient(good_routes()),
                   sleep=lambda s: None, clock=lambda: 0)


def test_output_never_contains_response_bodies_or_headers(capsys):
    routes = good_routes()
    routes[("https", FORMS, "/")] = smoke.Response(200, {**HSTS, "Set-Cookie": "session=secreto"}, b"contenido-secreto")
    smoke.main(ARGS, client=FakeClient(routes), sleep=lambda s: None, clock=lambda: 0)
    out = capsys.readouterr().out
    assert "secreto" not in out and "Set-Cookie" not in out


def test_smoke_script_is_recorded_in_the_orchestrator_evidence():
    import deploy_release as release
    name = "scripts/despliegue/smoke_readonly.py"
    assert name in release.ORCHESTRATOR_SOURCES
    assert (Path(__file__).resolve().parents[2] / name).is_file()


def test_orchestrator_accepts_the_smoke_command_for_prod():
    import deploy_release as release
    plan = {"environment": "prod", "account": "123456789012", "region": "us-east-1", "mode": "bootstrap",
            "previous_tag": "bootstrap-placeholder", "candidate_tag": SHA, "desired_count": 1,
            "expected_head": "head2", "previous_revisions": [],
            "digests": {k: "sha256:" + "a" * 64 for k in release.SERVICES},
            "smoke_command": ["python3", "scripts/despliegue/smoke_readonly.py"] + ARGS[:],
            "context": {k: "configured" for k in (
                "hostedZoneName", "hostedZoneId", "domainName", "portalDomainName", "keycloakDomainName",
                "certificateArn", "bedrockModelId", "zohoSecretYaExiste", "proveedorListasCautela",
                "habilitarNatEgress", "snsAlertasSub")}}
    release.validate_plan(plan)
    plan["smoke_mode"] = "manual"
    plan["smoke_command"] = []
    plan["manual_checks"] = list(release.MANUAL_CHECKS)
    with pytest.raises(release.MigrationError, match="solo habilitada en staging"):
        release.validate_plan(plan)
