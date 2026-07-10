#!/usr/bin/env python3
"""Validate declared environment variables by environment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RUNTIME_KEYS = {
    "APP_ENV",
    "AWS_REGION",
    "FRONTEND_URL",
    "PORTAL_INTERNO_URL",
    "SECRET_KEY",
    "UVICORN_WORKERS",
    "TRUSTED_PROXY_IPS",
    "STORAGE_BACKEND",
    "S3_BUCKET",
    "BEDROCK_MODEL_ID",
    "ZOHO_CLIENT_ID",
    "ZOHO_CLIENT_SECRET",
    "ZOHO_REFRESH_TOKEN",
    "ZOHO_REDIRECT_URI",
    "ZOHO_WEBHOOK_SECRET",
    "ZOHO_WEBHOOK_SIGNATURE_HEADER",
    "ZOHO_SIGN_TESTING",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
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
    "VITE_BACKEND_URL",
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
    ".env.dev.example": {"KEYCLOAK_DB_URL", "SNS_TOPIC_ARN"},
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
    forbidden_in_aws = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}

    for env_name, config in ENVIRONMENTS.items():
        file_reports: list[FileReport] = []
        for env_file, expected_file in config["files"].items():
            expected = set(config["required"])
            declared = parse_env_keys(ROOT / env_file)
            forbidden = declared & forbidden_in_aws if env_name in {"staging", "production"} else set()

            file_reports.append(
                FileReport(
                    env_file=env_file,
                    expected_file=expected_file,
                    exists=(ROOT / env_file).exists(),
                    present=sorted(declared & expected),
                    missing=sorted(expected - declared),
                    extra=sorted((declared - expected) - ALLOWED_EXTRA_KEYS.get(env_file, set())),
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
