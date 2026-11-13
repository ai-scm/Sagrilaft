#!/usr/bin/env python3
"""Validate declared environment variables by environment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_RUNTIME_KEYS = {
    "APP_ENV",
    "AWS_REGION",
    "FRONTEND_URL",
    "PORTAL_INTERNO_URL",
    "PORTAL_AUTH_DISABLED",
    "SECRET_KEY",
    "UVICORN_WORKERS",
    "TRUSTED_PROXY_IPS",
    "MAX_UPLOAD_SIZE_MB",
    "PROVEEDOR_LISTAS_CAUTELA",
    "SAGRILAFT_API_URL",
    "SAGRILAFT_API_KEY",
    # Listas v2 (ver docs/listas): modalidad, escenario del simulador, custodia y Tusdatos.
    "LISTAS_IMPLEMENTACION",
    "LISTAS_SIMULACION_ESCENARIO",
    "LISTAS_CUSTODIA_BACKEND",
    "LISTAS_TUSDATOS_URL",
    "LISTAS_TUSDATOS_TOKEN",
    "LISTAS_TUSDATOS_USUARIO",
    "LISTAS_TUSDATOS_CLAVE",
    "STORAGE_BACKEND",
    "BEDROCK_MODEL_ID",
    "BEDROCK_MAX_TOKENS",
    "BEDROCK_TEMPERATURE",
    "BEDROCK_CONNECT_TIMEOUT_SECONDS",
    "BEDROCK_READ_TIMEOUT_SECONDS",
    "BEDROCK_MAX_ATTEMPTS",
    "BEDROCK_PDF_MAX_PAGES",
    "BEDROCK_DEFAULT_CONFIDENCE",
    "BEDROCK_RESPONSE_LOG_CHARS",
    "ZOHO_CLIENT_ID",
    "ZOHO_CLIENT_SECRET",
    "ZOHO_REFRESH_TOKEN",
    "ZOHO_REDIRECT_URI",
    "ZOHO_WEBHOOK_SECRET",
    "ZOHO_WEBHOOK_SIGNATURE_HEADER",
    "ZOHO_SIGN_TESTING",
    "ZOHO_REFRESH_MARGIN_SECONDS",
    "ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS",
    "ZOHO_HTTP_MAX_ATTEMPTS",
    "ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS",
    "ZOHO_HTTP_BACKOFF_FACTOR",
    "ZOHO_TOKEN_TIMEOUT_SECONDS",
    "ZOHO_STATUS_TIMEOUT_SECONDS",
    "ZOHO_CANCEL_TIMEOUT_SECONDS",
    "ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS",
    "ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS",
    "ZOHO_DOWNLOAD_TIMEOUT_SECONDS",
    "ZOHO_SIGN_REQUEST_EXPIRATION_DAYS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_FROM",
    "SMTP_REPLY_TO",
    "SES_EMAIL_ORIGEN",
    "SES_NOTIFICACIONES_ENABLED",
    "ALERTAS_EMAIL_DESTINATARIO",
    "SNS_NOTIFICACIONES_ENABLED",
    "KEYCLOAK_ADMIN",
    "KEYCLOAK_ADMIN_PASSWORD",
    "KEYCLOAK_HOSTNAME",
    "KEYCLOAK_DB_USER",
    "KEYCLOAK_DB_PASSWORD",
    "KEYCLOAK_URL",
    "KEYCLOAK_REALM",
    "KEYCLOAK_CLIENT_ID",
    "KEYCLOAK_ISSUER_URL",
    "VITE_PORTAL_INTERNO_URL",
    "VITE_KEYCLOAK_URL",
    "VITE_KEYCLOAK_REALM",
    "VITE_KEYCLOAK_CLIENT_ID",
    "VITE_RAZON_SOCIAL",
    "VITE_CORREO_DATOS",
}

DEV_ONLY_KEYS = {
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "PORT_PUBLICO",
    "PORT_PORTAL",
    "AWS_PROFILE",
    # Credencial SES de desarrollo local; en staging/prod viene de Secrets Manager.
    "SMTP_USER",
    "SMTP_PASSWORD",
    # Solo alimenta el proxy del dev server de Vite (docker-compose.dev.yml);
    # en staging/prod el frontend usa /api relativo y el ALB enruta directo
    # al backend (infra/sagrilaft/lib/constructs/load-balancer.ts).
    "VITE_BACKEND_URL",
}

OPTIONAL_KEYS = {
    "JWKS_CACHE_TTL_SECONDS",
}

# En staging/producción, el valor real de estas variables en ECS lo escribe
# el CDK (SSM Parameter Store), no una persona — este validador no las exige
# por presencia de valor. Ver infra/sagrilaft/lib/constructs/config-parameters.ts
# y ecs-fargate.ts.
#
CDK_MANAGED_KEYS = {
    "SNS_TOPIC_ARN",
}

ENVIRONMENTS = {
    "dev": {
        "files": {
            ".env.dev.example": ".env.dev.example",
        },
        "required": EXPECTED_RUNTIME_KEYS | DEV_ONLY_KEYS,
    },
    "staging": {
        "files": {
            ".env.staging.example": ".env.staging.example",
        },
        "required": EXPECTED_RUNTIME_KEYS,
    },
    "production": {
        "files": {
            ".env.prod.example": ".env.prod.example",
        },
        "required": EXPECTED_RUNTIME_KEYS,
    },
}

ALLOWED_EXTRA_KEYS: dict[str, set[str]] = {
    # KEYCLOAK_DB_URL: solo la lee docker-compose.yml base (keycloak.KC_DB_URL).
    # docker-compose.dev.yml sobreescribe KC_DB_URL con un valor fijo, así que
    # en el flujo estándar de dev queda "sombreada", no sin uso — ver
    # docs/produccion/configuracion/VARIABLES_DE_ENTORNO.md.
    ".env.dev.example": {"KEYCLOAK_DB_URL"},
}


ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True)
class FileReport:
    env_file: str
    expected_file: str
    exists: bool
    present: list[str]
    missing: list[str]
    extra: list[str]
    forbidden: list[str]


def parse_env_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()

    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = ASSIGNMENT_RE.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def build_report() -> dict[str, list[FileReport]]:
    report: dict[str, list[FileReport]] = {}
    forbidden_in_aws = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "SMTP_USER", "SMTP_PASSWORD"}

    for env_name, config in ENVIRONMENTS.items():
        file_reports: list[FileReport] = []
        for env_file, expected_file in config["files"].items():
            expected = set(config["required"])
            declared = parse_env_keys(ROOT / env_file)
            forbidden = declared & forbidden_in_aws if env_name in {"staging", "production"} else set()
            allowed = expected | OPTIONAL_KEYS | CDK_MANAGED_KEYS | ALLOWED_EXTRA_KEYS.get(env_file, set())

            file_reports.append(
                FileReport(
                    env_file=env_file,
                    expected_file=expected_file,
                    exists=(ROOT / env_file).exists(),
                    present=sorted(declared & expected),
                    missing=sorted(expected - declared),
                    extra=sorted(declared - allowed),
                    forbidden=sorted(forbidden),
                )
            )
        report[env_name] = file_reports

    return report


def print_report(report: dict[str, list[FileReport]]) -> int:
    exit_code = 0
    print("Reporte de validacion .env")
    print("Criterio: presencia de variables declaradas; no se validan valores.")
    print("Produccion usa ECS + Secrets Manager/SSM; .env.prod.example es referencia, no runtime.\n")

    for env_name, file_reports in report.items():
        approved = all(item.exists and not item.missing and not item.forbidden for item in file_reports)
        if not approved:
            exit_code = 1

        print(f"[{env_name}] {'APROBADO' if approved else 'RECHAZADO'}")
        for item in file_reports:
            if not item.exists:
                print(f"  - {item.env_file}: FALTA ARCHIVO")
                continue
            print(
                f"  - {item.env_file}: presentes={len(item.present)} "
                f"faltantes={len(item.missing)} extras={len(item.extra)}"
            )
            if item.missing:
                print(f"    faltan: {', '.join(item.missing)}")
            if item.extra:
                print(f"    extras: {', '.join(item.extra)}")
            if item.forbidden:
                print(f"    prohibidas en AWS runtime: {', '.join(item.forbidden)}")
        print()

    return exit_code


def main() -> int:
    return print_report(build_report())


if __name__ == "__main__":
    raise SystemExit(main())
