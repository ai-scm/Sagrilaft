#!/usr/bin/env python3
"""Build and push ECS images to ECR using the local Docker daemon."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


class PrecondicionError(Exception):
    """Falló una verificación previa (env file, Docker, credenciales AWS) antes de tocar ECR."""


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


def verificar_env_file(path: Path) -> None:
    if not path.exists():
        raise PrecondicionError(
            f"No existe el archivo de variables de entorno: {path}\n"
            "   Verifica --env-file, o que estés parado en la raíz del proyecto."
        )


def verificar_docker() -> None:
    try:
        subprocess.run(
            ["docker", "info"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise PrecondicionError(
            "Docker no está disponible o el daemon no está corriendo.\n"
            "   Verifica que Docker Desktop / dockerd esté activo."
        ) from e


def obtener_cuenta_aws() -> str:
    try:
        return output(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise PrecondicionError(
            "Credenciales AWS inválidas, expiradas o AWS CLI no encontrado.\n"
            "   Corre `aws sso login` (o revisa AWS_PROFILE) e intenta de nuevo."
        ) from e


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

    env_file = ROOT / args.env_file

    # ── Pre-vuelo: nada de esto toca Docker/ECR todavía ─────────────────────
    try:
        verificar_env_file(env_file)
        env = parse_env(env_file)
        region = args.region or env.get("AWS_REGION") or "us-east-1"
        verificar_docker()
        account = obtener_cuenta_aws()
        tag = args.tag or output(["git", "rev-parse", "HEAD"])
    except PrecondicionError as e:
        print(f"\n❌ Verificación previa fallida: {e}\n", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Verificación previa fallida al ejecutar: {' '.join(e.cmd)}\n", file=sys.stderr)
        return 1

    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"

    print("── Pre-vuelo OK ─────────────────────────────────")
    print(f"  Entorno   : {args.environment}")
    print(f"  Cuenta AWS: {account}")
    print(f"  Región    : {region}")
    print(f"  Tag       : {tag}")
    print(f"  Registry  : {registry}")
    print("  Imágenes  : backend, formulario-publico, portal-interno, keycloak")
    print("──────────────────────────────────────────────────")

    try:
        login_ecr(region, registry)
    except subprocess.CalledProcessError:
        print(
            f"\n❌ No se pudo autenticar Docker contra ECR ({registry}).\n"
            "   Verifica permisos IAM (ecr:GetAuthorizationToken) de tu usuario/rol.\n",
            file=sys.stderr,
        )
        return 1

    repos = {
        "backend": f"sagrilaft-{args.environment}-backend",
        "formulario-publico": f"sagrilaft-{args.environment}-formulario-publico",
        "portal-interno": f"sagrilaft-{args.environment}-portal-interno",
        "keycloak": f"sagrilaft-{args.environment}-keycloak",
    }

    builds: list[tuple[str, list[str], str]] = [
        ("backend", ["./backend"], repos["backend"]),
        (
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
            repos["formulario-publico"],
        ),
        (
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
            repos["portal-interno"],
        ),
        (
            "keycloak",
            [
                "--build-arg",
                f"KEYCLOAK_PORTAL_URL={env.get('VITE_PORTAL_INTERNO_URL', 'https://sagrilaft.ia.blend360.com')}",
                "--build-arg",
                f"KEYCLOAK_FORMULARIO_URL={env.get('FRONTEND_URL', 'https://forms-sagrilaft.ia.blend360.com').split(',')[0]}",
                "./keycloak",
            ],
            repos["keycloak"],
        ),
    ]

    # ── Build & push con seguimiento explícito de éxito/fallo por imagen ────
    completadas: set[str] = set()
    fallidas: set[str] = set()

    for nombre, docker_args, repo in builds:
        try:
            build_and_push(nombre, docker_args, repo, registry, tag)
            completadas.add(nombre)
        except subprocess.CalledProcessError:
            fallidas.add(nombre)
            break  # fail-fast: no tiene sentido construir lo que sigue si ya falló una

    todos_los_nombres = [nombre for nombre, _, _ in builds]
    no_intentadas = [n for n in todos_los_nombres if n not in completadas and n not in fallidas]

    print("\n── Resumen de build & push ──────────────────────")
    for nombre in todos_los_nombres:
        if nombre in completadas:
            print(f"  ✅ {nombre}")
        elif nombre in fallidas:
            print(f"  ❌ {nombre}  (FALLÓ — ver error arriba)")
        else:
            print(f"  ⏭  {nombre}  (no intentado)")
    print("──────────────────────────────────────────────────")

    if fallidas or no_intentadas:
        print(
            f"\n🛑 El tag {tag} quedó INCOMPLETO en ECR "
            f"({len(completadas)}/{len(todos_los_nombres)} imágenes listas).\n"
            "   NO EJECUTES EL DEPLOY: los 4 servicios de ECS deben compartir "
            "exactamente el mismo tag, o AWS activará el Circuit Breaker y hará rollback.\n"
            "   Corrige el error de arriba y vuelve a correr ESTE SCRIPT COMPLETO — "
            "es idempotente, Docker reutiliza la caché de las imágenes ya construidas, "
            "no hace falta limpiar nada en ECR a mano.\n",
            file=sys.stderr,
        )
        return 1

    print(
        f"\n✅ Las 4 imágenes quedaron listas con tag {tag}. "
        "Seguro continuar con el paso 2 de GUIA_DESPLIEGUE_LOCAL.md (deploy CDK).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
