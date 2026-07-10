#!/usr/bin/env python3
"""Build and push ECS images to ECR using the local Docker daemon."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
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


def output(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def run(command: list[str]) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    subprocess.run(command, cwd=ROOT, check=True)


def login_ecr(region: str, registry: str) -> None:
    password = subprocess.check_output(["aws", "ecr", "get-login-password", "--region", region], text=True)
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=password,
        text=True,
        check=True,
    )


def build_and_push(name: str, docker_args: list[str], repo: str, registry: str, tag: str) -> None:
    image = f"{registry}/{repo}"
    print(f"\n== {name}: {image}:{tag}")
    run(["docker", "build", *docker_args, "-t", f"{image}:{tag}", "-t", f"{image}:latest"])
    run(["docker", "push", f"{image}:{tag}"])
    run(["docker", "push", f"{image}:latest"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.prod")
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--region", default=None)
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()

    env = parse_env(ROOT / args.env_file)
    region = args.region or env.get("AWS_REGION") or "us-east-1"
    account = output(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"
    tag = args.tag or output(["git", "rev-parse", "HEAD"])

    login_ecr(region, registry)

    repos = {
        "backend": f"sagrilaft-{args.environment}-backend",
        "formulario": f"sagrilaft-{args.environment}-formulario-publico",
        "portal": f"sagrilaft-{args.environment}-portal-interno",
        "keycloak": f"sagrilaft-{args.environment}-keycloak",
    }

    build_and_push("backend", ["./backend"], repos["backend"], registry, tag)
    build_and_push(
        "formulario-publico",
        [
            "--build-arg",
            f"VITE_BACKEND_URL={env.get('VITE_BACKEND_URL', '')}",
            "--build-arg",
            f"VITE_PORTAL_INTERNO_URL={env.get('VITE_PORTAL_INTERNO_URL', '')}",
            "--build-arg",
            f"VITE_RAZON_SOCIAL={env.get('VITE_RAZON_SOCIAL', 'HIGH TECH SOFTWARE S.A.S')}",
            "--build-arg",
            f"VITE_CORREO_DATOS={env.get('VITE_CORREO_DATOS', 'administrativocol@blend360.com')}",
            "-f",
            "./frontend/apps/formulario-publico/Dockerfile",
            "./frontend",
        ],
        repos["formulario"],
        registry,
        tag,
    )
    build_and_push(
        "portal-interno",
        [
            "--build-arg",
            f"VITE_BACKEND_URL={env.get('VITE_BACKEND_URL', '')}",
            "--build-arg",
            f"VITE_KEYCLOAK_URL={env.get('VITE_KEYCLOAK_URL', '')}",
            "--build-arg",
            f"VITE_KEYCLOAK_REALM={env.get('VITE_KEYCLOAK_REALM', 'sagrilaft')}",
            "--build-arg",
            f"VITE_KEYCLOAK_CLIENT_ID={env.get('VITE_KEYCLOAK_CLIENT_ID', 'sagrilaft-portal')}",
            "-f",
            "./frontend/apps/portal-interno/Dockerfile",
            "./frontend",
        ],
        repos["portal"],
        registry,
        tag,
    )
    build_and_push(
        "keycloak",
        [
            "--build-arg",
            f"KEYCLOAK_PORTAL_URL={env.get('VITE_PORTAL_INTERNO_URL', 'https://sagrilaft.ia.blend360.com')}",
            "--build-arg",
            f"KEYCLOAK_FORMULARIO_URL={env.get('FRONTEND_URL', 'https://forms-sagrilaft.ia.blend360.com').split(',')[0]}",
            "./keycloak",
        ],
        repos["keycloak"],
        registry,
        tag,
    )

    print(f"\nPushed images with tag: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
