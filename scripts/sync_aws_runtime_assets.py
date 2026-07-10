#!/usr/bin/env python3
"""Sync production runtime secrets and ECR repositories in AWS.

Values are read from .env.prod by default. Secret values are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


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


def secret_exists(name: str, region: str) -> bool:
    result = run(["secretsmanager", "describe-secret", "--secret-id", name], region=region)
    return result.returncode == 0


def upsert_secret(name: str, payload: dict[str, str], region: str) -> str:
    if secret_exists(name, region):
        result = run(
            ["secretsmanager", "put-secret-value", "--secret-id", name],
            region=region,
            input_file_payload=payload,
        )
        action = "updated"
    else:
        result = run(
            ["secretsmanager", "create-secret", "--name", name],
            region=region,
            input_file_payload=payload,
        )
        action = "created"

    if result.returncode != 0:
        raise RuntimeError(f"Failed to sync secret {name}: {result.stderr.strip()}")
    return action


def ecr_repo_exists(name: str, region: str) -> bool:
    result = run(["ecr", "describe-repositories", "--repository-names", name], region=region)
    return result.returncode == 0


def ensure_ecr_repo(name: str, region: str) -> str:
    if ecr_repo_exists(name, region):
        return "exists"
    result = run(
        [
            "ecr",
            "create-repository",
            "--repository-name",
            name,
            "--image-scanning-configuration",
            "scanOnPush=true",
        ],
        region=region,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create ECR repo {name}: {result.stderr.strip()}")
    return "created"


def required(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if value == "":
        raise RuntimeError(f"Missing required value in env file: {key}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    env = parse_env(ROOT / args.env_file)
    region = args.region or env.get("AWS_REGION") or "us-east-1"
    prefix = f"sagrilaft/{args.environment}"

    secrets = {
        f"{prefix}/app_secret": {"secret_key": required(env, "SECRET_KEY")},
        f"{prefix}/zoho_credentials": {
            "client_id": required(env, "ZOHO_CLIENT_ID"),
            "client_secret": required(env, "ZOHO_CLIENT_SECRET"),
            "refresh_token": required(env, "ZOHO_REFRESH_TOKEN"),
            "webhook_secret": required(env, "ZOHO_WEBHOOK_SECRET"),
        },
        f"{prefix}/smtp_credentials": {
            "username": required(env, "SMTP_USER"),
            "password": required(env, "SMTP_PASSWORD"),
        },
        f"{prefix}/keycloak_admin": {
            "username": env.get("KEYCLOAK_ADMIN") or "admin",
            "password": required(env, "KEYCLOAK_ADMIN_PASSWORD"),
        },
        f"{prefix}/db_credentials": {
            "username": required(env, "KEYCLOAK_DB_USER"),
            "password": required(env, "KEYCLOAK_DB_PASSWORD"),
        },
    }

    repositories = [
        f"sagrilaft-{args.environment}-backend",
        f"sagrilaft-{args.environment}-formulario-publico",
        f"sagrilaft-{args.environment}-portal-interno",
        f"sagrilaft-{args.environment}-keycloak",
    ]

    print(f"Syncing AWS runtime assets in {region} for {args.environment}")
    for name, payload in secrets.items():
        print(f"secret {name}: {upsert_secret(name, payload, region)}")

    for name in repositories:
        print(f"ecr {name}: {ensure_ecr_repo(name, region)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
