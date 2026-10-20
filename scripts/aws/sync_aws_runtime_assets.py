#!/usr/bin/env python3
"""Sincroniza en Secrets Manager SOLO las credenciales externas a CDK.

Secretos externos (credenciales que no genera CDK; CDK los crea vacíos o los
importa con `zohoSecretYaExiste`). Deben existir antes de ejecutar este script:
  - zoho_credentials
  - smtp_credentials
  - sagrilaft_listas_cautela_credentials (solo con PROVEEDOR_LISTAS_CAUTELA=sagrilaft
    y SAGRILAFT_API_KEY con valor real)

Secretos administrados por CDK (app_secret, db_credentials, keycloak_admin).
Este script NUNCA los escribe: sobrescribirlos desincroniza la contraseña real de
RDS y la de Keycloak. Ver docs/produccion/configuracion/MATRIZ_AWS_CONFIG.md.

Modo por defecto: dry-run (solo lee AWS y muestra qué haría).
Para escribir: --apply --expected-account <id de la cuenta objetivo>.
Los valores secretos nunca se imprimen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")

# APP_ENV que debe declarar el archivo de entorno para cada --environment.
APP_ENV_BY_ENVIRONMENT = {"prod": "production", "staging": "staging"}

# Campo del secreto -> variable del archivo de entorno.
EXTERNAL_SECRETS: dict[str, dict[str, str]] = {
    "zoho_credentials": {
        "client_id": "ZOHO_CLIENT_ID",
        "client_secret": "ZOHO_CLIENT_SECRET",
        "refresh_token": "ZOHO_REFRESH_TOKEN",
        "webhook_secret": "ZOHO_WEBHOOK_SECRET",
    },
    "smtp_credentials": {
        "username": "SMTP_USER",
        "password": "SMTP_PASSWORD",
    },
}

# Solo se escribe si la variable tiene un valor real (no vacío ni REPLACE_*).
OPTIONAL_EXTERNAL_SECRETS: dict[str, dict[str, str]] = {
    "sagrilaft_listas_cautela_credentials": {
        "api_key": "SAGRILAFT_API_KEY",
    },
}

# Administrados por CDK: se listan para informar, nunca se escriben.
CDK_MANAGED_SECRETS = ("app_secret", "db_credentials", "keycloak_admin")

REPOSITORY_TEMPLATES = (
    "sagrilaft-{env}-backend",
    "sagrilaft-{env}-formulario-publico",
    "sagrilaft-{env}-portal-interno",
    "sagrilaft-{env}-keycloak",
)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT_RE.match(raw_line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def run(command: list[str], *, region: str, input_file_payload: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_command = ["aws", *command, "--region", region]
    temp_path: Path | None = None
    if input_file_payload is not None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp_file:
            json.dump(input_file_payload, temp_file)
            temp_path = Path(temp_file.name)
        os.chmod(temp_path, 0o600)
        full_command.extend(["--secret-string", f"file://{temp_path}"])

    try:
        return subprocess.run(full_command, check=False, text=True, capture_output=True)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def account_id(region: str) -> str:
    result = run(["sts", "get-caller-identity", "--query", "Account", "--output", "text"], region=region)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo identificar la cuenta AWS: {result.stderr.strip()}")
    return result.stdout.strip()


def secret_exists(name: str, region: str) -> bool:
    result = run(["secretsmanager", "describe-secret", "--secret-id", name], region=region)
    return result.returncode == 0


def put_secret(name: str, payload: dict[str, str], region: str) -> None:
    # Solo put-secret-value: nunca create-secret. El secreto debe existir ya (lo crea CDK).
    result = run(
        ["secretsmanager", "put-secret-value", "--secret-id", name],
        region=region,
        input_file_payload=payload,
    )
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo actualizar {name}: {result.stderr.strip()}")


def repo_exists(name: str, region: str) -> bool:
    result = run(["ecr", "describe-repositories", "--repository-names", name], region=region)
    return result.returncode == 0


def required(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if value == "":
        raise RuntimeError(f"Falta un valor obligatorio en el archivo de entorno: {key}")
    if value.startswith("REPLACE_"):
        raise RuntimeError(f"{key} aún tiene un marcador REPLACE_*; reemplácelo antes de sincronizar.")
    return value


def build_payload(env: dict[str, str], fields: dict[str, str]) -> dict[str, str]:
    return {field: required(env, var) for field, var in fields.items()}


def build_optional_payload(env: dict[str, str], fields: dict[str, str]) -> dict[str, str] | None:
    values = {}
    for field, var in fields.items():
        value = env.get(var, "")
        if value == "" or value.startswith("REPLACE_"):
            return None
        values[field] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--environment", choices=sorted(APP_ENV_BY_ENVIRONMENT), default="prod")
    parser.add_argument("--region", default=None)
    parser.add_argument("--apply", action="store_true", help="Escribe en AWS. Sin esta bandera solo se muestra el plan.")
    parser.add_argument("--expected-account", default=None, help="ID de la cuenta AWS objetivo; obligatorio con --apply.")
    args = parser.parse_args()

    if args.apply and not args.expected_account:
        parser.error("--apply requiere --expected-account con el ID de la cuenta objetivo.")

    env = parse_env(ROOT / args.env_file)
    expected_app_env = APP_ENV_BY_ENVIRONMENT[args.environment]
    if env.get("APP_ENV") != expected_app_env:
        raise SystemExit(
            f"{args.env_file} declara APP_ENV={env.get('APP_ENV')!r}, pero --environment {args.environment} "
            f"requiere APP_ENV={expected_app_env!r}. No se hace nada."
        )

    region = args.region or env.get("AWS_REGION") or "us-east-1"
    prefix = f"sagrilaft/{args.environment}"
    mode = "APPLY" if args.apply else "DRY-RUN (sin cambios)"
    print(f"Sincronización de secretos externos en {region} para {args.environment} — modo {mode}")

    if args.apply:
        caller = account_id(region)
        if caller != args.expected_account:
            raise SystemExit(f"La cuenta activa ({caller}) no coincide con --expected-account. No se escribe nada.")
        print(f"Cuenta verificada: {caller}")

    errors = 0

    for name, fields in EXTERNAL_SECRETS.items():
        full_name = f"{prefix}/{name}"
        try:
            payload = build_payload(env, fields)
        except RuntimeError as exc:
            print(f"secret {full_name}: ERROR - {exc}")
            errors += 1
            continue
        if not secret_exists(full_name, region):
            print(f"secret {full_name}: ERROR - no existe. Ejecute cdk deploy primero (CDK lo crea vacío).")
            errors += 1
            continue
        if not args.apply:
            print(f"secret {full_name}: se actualizaría (campos: {', '.join(sorted(payload))})")
            continue
        put_secret(full_name, payload, region)
        print(f"secret {full_name}: actualizado (campos: {', '.join(sorted(payload))})")

    for name, fields in OPTIONAL_EXTERNAL_SECRETS.items():
        full_name = f"{prefix}/{name}"
        provider = env.get("PROVEEDOR_LISTAS_CAUTELA", "")
        if provider != "sagrilaft":
            print(f"secret {full_name}: omitido (PROVEEDOR_LISTAS_CAUTELA={provider or 'vacío'}; solo se carga con 'sagrilaft')")
            continue
        payload = build_optional_payload(env, fields)
        if payload is None:
            print(f"secret {full_name}: omitido (sin valor real en el archivo de entorno)")
            continue
        if not secret_exists(full_name, region):
            print(f"secret {full_name}: ERROR - no existe. Ejecute cdk deploy primero.")
            errors += 1
            continue
        if not args.apply:
            print(f"secret {full_name}: se actualizaría (campos: {', '.join(sorted(payload))})")
            continue
        put_secret(full_name, payload, region)
        print(f"secret {full_name}: actualizado (campos: {', '.join(sorted(payload))})")

    for name in CDK_MANAGED_SECRETS:
        print(f"secret {prefix}/{name}: administrado por CDK, NO se escribe desde este script")

    for template in REPOSITORY_TEMPLATES:
        repo = template.format(env=args.environment)
        status = "existe" if repo_exists(repo, region) else "NO existe (lo crea CDK)"
        print(f"ecr {repo}: {status}")

    if errors:
        print(f"\nTerminado con {errors} error(es). Revise los mensajes anteriores.")
        return 1
    print("\nTerminado." if args.apply else "\nDry-run terminado. Para escribir, repita con --apply --expected-account <id>.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
