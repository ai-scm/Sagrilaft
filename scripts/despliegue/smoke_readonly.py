#!/usr/bin/env python3
"""Smoke test de solo lectura para validar una release activada.

Pensado para `smoke_command` de deploy_release.py. Solo emite GET sin cuerpo, sin
credenciales ni cookies: no crea accesos, no envía correos y no modifica estado.
Comprueba, por dominio: redirección HTTP→HTTPS, respuesta HTTPS y encabezado HSTS;
en los dominios del backend, `/health` con el commit candidato y la base de datos
operativa; y en Keycloak, el documento OIDC del realm.

No sustituye la validación funcional con correo real (P07) ni la firma (P05).
"""
import argparse
import http.client
import json
import os
import re
import ssl
import sys
import time

HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
REALM_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REDIRECT_STATUSES = (301, 302, 307, 308)
READ_ONLY_METHODS = ("GET",)
MAX_BODY = 1_000_000
MIN_HSTS_SECONDS = 31536000


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body


class HttpClient:
    """Cliente mínimo: no sigue redirecciones y solo admite métodos de lectura."""

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.methods_used = set()

    def request(self, method, scheme, host, path):
        if method not in READ_ONLY_METHODS:
            raise ValueError(f"Método no permitido en un smoke de solo lectura: {method}")
        self.methods_used.add(method)
        if scheme == "https":
            conn = http.client.HTTPSConnection(host, timeout=self.timeout, context=ssl.create_default_context())
        elif scheme == "http":
            conn = http.client.HTTPConnection(host, timeout=self.timeout)
        else:
            raise ValueError("Esquema no admitido")
        try:
            conn.request(method, path, headers={"User-Agent": "sagrilaft-smoke-readonly/1", "Accept": "*/*"})
            raw = conn.getresponse()
            body = raw.read(MAX_BODY)
            return Response(raw.status, dict(raw.getheaders()), body)
        finally:
            conn.close()


def _json_body(response):
    try:
        value = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _hsts_ok(response):
    header = response.headers.get("strict-transport-security", "")
    match = re.search(r"max-age=(\d+)", header, re.IGNORECASE)
    return bool(match) and int(match.group(1)) >= MIN_HSTS_SECONDS


def _safe(name, check):
    try:
        ok, detail = check()
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        ok, detail = False, f"error de conexión: {type(exc).__name__}"
    return {"check": name, "ok": bool(ok), "detail": detail}


def check_http_redirect(client, domain):
    response = client.request("GET", "http", domain, "/")
    location = response.headers.get("location", "")
    ok = response.status in REDIRECT_STATUSES and location.startswith(f"https://{domain}")
    return ok, f"HTTP {response.status}" + ("" if ok else " sin redirección a https del mismo dominio")


def check_https(client, domain, exact_ok):
    response = client.request("GET", "https", domain, "/")
    status_ok = response.status == 200 if exact_ok else 200 <= response.status < 400
    return status_ok, f"HTTPS {response.status}", response


def check_health(client, domain, sha):
    response = client.request("GET", "https", domain, "/health")
    body = _json_body(response)
    if response.status != 200 or body is None:
        return False, f"HTTP {response.status} sin JSON válido"
    problems = []
    if body.get("status") != "healthy":
        problems.append("status distinto de healthy")
    if body.get("commit") != sha:
        problems.append("commit no coincide con el candidato")
    dependencies = body.get("dependencies")
    if not isinstance(dependencies, dict) or dependencies.get("database") != "ok":
        problems.append("base de datos no operativa")
    return not problems, "; ".join(problems) or "healthy, commit y base de datos correctos"


def check_oidc(client, domain, realm):
    response = client.request("GET", "https", domain, f"/realms/{realm}/.well-known/openid-configuration")
    body = _json_body(response)
    if response.status != 200 or body is None:
        return False, f"HTTP {response.status} sin JSON válido"
    expected = f"https://{domain}/realms/{realm}"
    ok = body.get("issuer") == expected
    return ok, "issuer correcto" if ok else "issuer no coincide con el dominio y realm esperados"


def run_checks(client, cfg):
    results = []
    domains = (("formulario", cfg["forms_domain"], True), ("portal", cfg["portal_domain"], True),
               ("keycloak", cfg["keycloak_domain"], False))
    for label, domain, exact_ok in domains:
        results.append(_safe(f"{label}: redirección HTTP→HTTPS", lambda d=domain: check_http_redirect(client, d)))
        https = {}

        def fetch(d=domain, e=exact_ok, store=https):
            ok, detail, response = check_https(client, d, e)
            store["response"] = response
            return ok, detail

        results.append(_safe(f"{label}: respuesta HTTPS", fetch))
        response = https.get("response")
        ok = response is not None and _hsts_ok(response)
        results.append({"check": f"{label}: HSTS (max-age >= {MIN_HSTS_SECONDS})", "ok": ok,
                        "detail": "presente" if ok else "ausente o insuficiente"})
    for label, domain in (("formulario", cfg["forms_domain"]), ("portal", cfg["portal_domain"])):
        results.append(_safe(f"{label}: /health", lambda d=domain: check_health(client, d, cfg["sha"])))
    results.append(_safe("keycloak: documento OIDC del realm",
                         lambda: check_oidc(client, cfg["keycloak_domain"], cfg["realm"])))
    return results


def smoke(client, cfg, sleep=time.sleep, clock=time.monotonic):
    """Repite todas las comprobaciones hasta que pasen o venza el plazo."""
    deadline = clock() + cfg["timeout"]
    attempts = 0
    while True:
        attempts += 1
        results = run_checks(client, cfg)
        passed = all(r["ok"] for r in results)
        if passed or clock() + cfg["interval"] > deadline:
            break
        sleep(cfg["interval"])
    return {"environment": cfg["environment"], "sha": cfg["sha"], "readonly": True,
            "methods_used": sorted(getattr(client, "methods_used", set())), "attempts": attempts,
            "passed": passed, "results": results}


def _host(value):
    if not HOST_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("Dominio inválido: usar solo el nombre de host, en minúsculas")
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Smoke test de solo lectura de una release activada")
    parser.add_argument("--environment", choices=("staging", "prod"), required=True)
    parser.add_argument("--sha", required=True, help="SHA completo de la release candidata")
    parser.add_argument("--forms-domain", type=_host, required=True)
    parser.add_argument("--portal-domain", type=_host, required=True)
    parser.add_argument("--keycloak-domain", type=_host, required=True)
    parser.add_argument("--realm", default="sagrilaft")
    parser.add_argument("--timeout", type=int, default=240, help="Plazo total en segundos (por defecto 240)")
    parser.add_argument("--interval", type=int, default=10, help="Espera entre intentos (por defecto 10)")
    parser.add_argument("--evidence-file", help="Ruta nueva donde guardar el resultado JSON")
    args = parser.parse_args(argv)
    if not SHA_RE.fullmatch(args.sha):
        parser.error("--sha debe ser un SHA completo de 40 caracteres hexadecimales")
    if not REALM_RE.fullmatch(args.realm):
        parser.error("--realm inválido")
    if not 1 <= args.timeout <= 540 or not 1 <= args.interval <= 60:
        parser.error("--timeout debe estar entre 1 y 540 y --interval entre 1 y 60")
    if len({args.forms_domain, args.portal_domain, args.keycloak_domain}) != 3:
        parser.error("Los tres dominios deben ser distintos")
    return args


def main(argv=None, client=None, sleep=time.sleep, clock=time.monotonic):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    cfg = {"environment": args.environment, "sha": args.sha, "forms_domain": args.forms_domain,
           "portal_domain": args.portal_domain, "keycloak_domain": args.keycloak_domain, "realm": args.realm,
           "timeout": args.timeout, "interval": args.interval}
    summary = smoke(client or HttpClient(), cfg, sleep=sleep, clock=clock)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.evidence_file:
        fd = os.open(args.evidence_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(text + "\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
