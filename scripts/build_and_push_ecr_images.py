#!/usr/bin/env python3
"""Publica cuatro imágenes por SHA sin reemplazar tags.

--manifest crea evidencia nueva, incluidos resultados parciales.
--reuse-manifest acepta explícitamente evidencia previa revisada.
No adopta imágenes existentes sin evidencia ni despliega infraestructura.
Ejecutar este publicador sí usa AWS y Docker; los tests sustituyen ambos.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("backend", "formulario-publico", "portal-interno", "keycloak")
ACTIVE_LOCK = ContextVar("publication_lock_fd", default=None)
LOCK_DIRECTORY = Path("/tmp")  # Shared across checkouts; never use a checkout-local lock.
PLATFORM = "linux/amd64"  # Arquitectura x86 predeterminada del Fargate actual.
ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


class PrecondicionError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise PrecondicionError(message)


def parse_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ASSIGNMENT_RE.match(line)
        if match:
            key, value = match.groups()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def lock_descriptors():
    fd = ACTIVE_LOCK.get()
    return () if fd is None else (fd,)


def output(command):
    return subprocess.check_output(command, cwd=ROOT, text=True, pass_fds=lock_descriptors()).strip()


def run(command, cwd=None):
    subprocess.run(command, cwd=cwd or ROOT, check=True, pass_fds=lock_descriptors())


@contextmanager
def publication_lock(registry, tag):
    """Fail closed for concurrent local publishers, including different checkouts.

    Keep the inode after releasing: unlinking would let contenders lock different
    files. Other users unable to open the 0600 file must stop, not bypass it.
    """
    key = hashlib.sha256(f"{registry}:{tag}".encode()).hexdigest()
    path = LOCK_DIRECTORY / f"sagrilaft-publication-{key}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PrecondicionError("Otra publicación local tiene el lock de esta release; no se inicia Docker") from error
        token = ACTIVE_LOCK.set(fd)
        try:
            yield
        finally:
            ACTIVE_LOCK.reset(token)
    finally:
        # No explicit LOCK_UN: build/push children inherit the descriptor and
        # keep the lock if the parent exits while they are still running.
        os.close(fd)


def validate_source(tag):
    head = output(["git", "rev-parse", "HEAD"])
    tag = head if tag is None else tag
    require(bool(re.fullmatch(r"[a-f0-9]{40}", tag)), "El tag debe ser SHA completo, no latest ni alias")
    require(tag == head, "El SHA solicitado no coincide con HEAD")
    require(not output(["git", "status", "--porcelain", "--untracked-files=all"]),
            "Checkout modificado o con archivos sin registrar; confirmar los cambios antes de publicar")
    stages = output(["git", "ls-files", "--stage", "--", "backend", "frontend", "keycloak"])
    require(not any(line.startswith("160000 ") for line in stages.splitlines()), "Submódulos en contextos no soportados")
    return tag


@contextmanager
def source_snapshot(tag):
    # No incorporar .env ignorados, uploads ni artefactos locales al contexto.
    with tempfile.TemporaryDirectory(prefix="sagrilaft-build-") as directory:
        path = Path(directory)
        archive = path / "source.tar"
        run(["git", "archive", "--format=tar", "--output", str(archive), tag, "backend", "frontend", "keycloak"])
        with tarfile.open(archive) as stream:
            stream.extractall(path, filter="data")
        archive.unlink()
        yield path


def builds(env):
    def value(key, default=None):
        result = env.get(key, default)
        require(isinstance(result, str) and bool(result.strip()), f"Falta configuración de build: {key}")
        return result
    # An explicit empty origin selects same-origin /api in staging/prod.
    # A missing key remains an error: do not hide incomplete build configuration.
    backend = env.get("VITE_BACKEND_URL")
    require(isinstance(backend, str) and (backend == "" or bool(backend.strip())),
            "Falta configuración de build: VITE_BACKEND_URL (vacío explícito permitido)")
    portal = value("VITE_PORTAL_INTERNO_URL")
    form = env.get("KEYCLOAK_FORMULARIO_URL") or env.get("FRONTEND_URL", "").split(",")[0]
    arguments = {
        "backend": {},
        "formulario-publico": {
            "VITE_BACKEND_URL": backend, "VITE_PORTAL_INTERNO_URL": portal,
            "VITE_RAZON_SOCIAL": value("VITE_RAZON_SOCIAL", "HIGH TECH SOFTWARE S.A.S"),
            "VITE_CORREO_DATOS": value("VITE_CORREO_DATOS", "administrativocol@blend360.com"),
        },
        "portal-interno": {
            "VITE_BACKEND_URL": backend, "VITE_KEYCLOAK_URL": value("VITE_KEYCLOAK_URL"),
            "VITE_KEYCLOAK_REALM": value("VITE_KEYCLOAK_REALM", "sagrilaft"),
            "VITE_KEYCLOAK_CLIENT_ID": value("VITE_KEYCLOAK_CLIENT_ID", "sagrilaft-portal"),
        },
        "keycloak": {
            "KEYCLOAK_PORTAL_URL": env.get("KEYCLOAK_PORTAL_URL") or portal,
            "KEYCLOAK_FORMULARIO_URL": value("KEYCLOAK_FORMULARIO_URL", form),
        },
    }
    result = {}
    for name in COMPONENTS:
        options = ["--platform", PLATFORM]
        for key, val in arguments[name].items():
            options += ["--build-arg", f"{key}={val}"]
        if name in ("formulario-publico", "portal-interno"):
            options += ["-f", f"./frontend/apps/{name}/Dockerfile", "./frontend"]
        else:
            options += [f"./{name}"]
        result[name] = options
    return result


def inputs_hash(tag, options):
    return hashlib.sha256(json.dumps([tag, options], ensure_ascii=False).encode()).hexdigest()


class Ecr:
    def __init__(self, region):
        self.region = region

    def call(self, service, operation, *args, allow_missing=False):
        response = subprocess.run(["aws", service, operation, *args, "--region", self.region,
                                   "--output", "json", "--no-cli-pager"], cwd=ROOT, text=True, capture_output=True)
        if response.returncode:
            if allow_missing and "An error occurred (ImageNotFoundException)" in response.stderr:
                return None
            raise PrecondicionError(f"AWS {service}/{operation} falló; no se asume ausencia de imagen")
        data = json.loads(response.stdout)
        require(isinstance(data, dict), "Respuesta AWS inválida")
        return data

    def digest(self, repo, tag):
        data = self.call("ecr", "describe-images", "--repository-name", repo,
                         "--image-ids", f"imageTag={tag}", allow_missing=True)
        if data is None:
            return None
        images = data.get("imageDetails", [])
        require(len(images) == 1 and bool(re.fullmatch(r"sha256:[a-f0-9]{64}", images[0].get("imageDigest", ""))),
                "Digest ECR ausente o inválido")
        return images[0]["imageDigest"]

    def immutable(self, repo):
        repositories = self.call("ecr", "describe-repositories", "--repository-names", repo).get("repositories", [])
        require(len(repositories) == 1 and repositories[0].get("imageTagMutability") == "IMMUTABLE",
                f"Repositorio {repo} no es IMMUTABLE; aplicar esa política por separado")


def save_manifest(path, manifest):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".manifest-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def login_ecr(region, registry):
    password = subprocess.check_output(["aws", "ecr", "get-login-password", "--region", region], text=True)
    subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin", registry],
                   input=password, text=True, check=True)


def publish(environment, account, region, tag, options, manifest_path, approved=None, api=None):
    api = api or Ecr(region)
    manifest = {"version": 1, "environment": environment, "account": account, "region": region,
                "tag": tag, "platform": PLATFORM, "complete": False, "images": {}}
    if approved is not None:
        require(isinstance(approved, dict), "Manifiesto aprobado inválido")
        require(all(approved.get(k) == manifest[k] for k in ("version", "environment", "account", "region", "tag", "platform")),
                "El manifiesto aprobado pertenece a otra release/ambiente/plataforma")
        require(isinstance(approved.get("images"), dict) and set(approved["images"]).issubset(COMPONENTS), "Manifiesto aprobado inválido")
    with manifest_path.open("x"):
        pass  # Nunca sobrescribir un manifiesto previo o el usado para reintentar.
    save_manifest(manifest_path, manifest)
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"
    existing = {}
    try:
        require(api.call("sts", "get-caller-identity").get("Account") == account, "Cuenta activa distinta de --account")
        for name in COMPONENTS:
            repo = f"sagrilaft-{environment}-{name}"
            api.immutable(repo)
            digest = api.digest(repo, tag)
            evidence = approved["images"].get(name) if approved else None
            if digest is not None:
                require(isinstance(evidence, dict) and evidence.get("digest") == digest
                        and evidence.get("repository") == f"{registry}/{repo}"
                        and evidence.get("inputsHash") == inputs_hash(tag, options[name]),
                        f"{name}: tag existente sin evidencia coincidente; no se reemplaza ni adopta automáticamente")
                existing[name] = digest
                manifest["images"][name] = {"repository": f"{registry}/{repo}", "digest": digest,
                                            "inputsHash": inputs_hash(tag, options[name]), "status": "reused"}
                save_manifest(manifest_path, manifest)
            else:
                require(evidence is None, f"{name}: imagen acreditada ya no existe; reconciliar")
        missing = [name for name in COMPONENTS if name not in existing]
        if missing:
            with publication_lock(registry, tag):
                run(["docker", "info"])
                login_ecr(region, registry)
                with source_snapshot(tag) as source:
                    for name in missing:
                        repo = f"sagrilaft-{environment}-{name}"
                        uri = f"{registry}/{repo}"
                        print(f"Publicando {name}:{tag}", flush=True)
                        api.immutable(repo)
                        require(api.digest(repo, tag) is None, f"{name}: publicación concurrente; reconciliar")
                        run(["docker", "build", *options[name], "-t", f"{uri}:{tag}"], cwd=source)
                        run(["docker", "push", f"{uri}:{tag}"], cwd=source)
                        digest = api.digest(repo, tag)
                        local = json.loads(output(["docker", "image", "inspect", f"{uri}:{tag}", "--format", "{{json .RepoDigests}}"]))
                        require(digest is not None and isinstance(local, list) and f"{uri}@{digest}" in local,
                                f"{name}: digest remoto no acreditado para la imagen publicada")
                        manifest["images"][name] = {"repository": uri, "digest": digest,
                                                    "inputsHash": inputs_hash(tag, options[name]), "status": "published"}
                        save_manifest(manifest_path, manifest)
        for name in COMPONENTS:
            api.immutable(f"sagrilaft-{environment}-{name}")
            require(api.digest(f"sagrilaft-{environment}-{name}", tag) == manifest["images"][name]["digest"], "Imagen cambió durante la publicación")
        manifest["digests"] = {name: manifest["images"][name]["digest"] for name in COMPONENTS}
        manifest["complete"] = True
        save_manifest(manifest_path, manifest)
        print(f"Cuatro imágenes acreditadas. Manifiesto: {manifest_path}. No se ha ejecutado ni autorizado un deploy.")
        return manifest
    except BaseException:
        manifest["complete"] = False
        manifest["result"] = "failed_or_uncertain"
        save_manifest(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    config = parser.add_mutually_exclusive_group()
    config.add_argument("--env-file", type=Path)
    config.add_argument("--from-environment", action="store_true", help="Leer configuración del proceso (CI)")
    parser.add_argument("--environment", choices=("staging", "prod"), required=True)
    parser.add_argument("--account", required=True, help="Cuenta AWS esperada")
    parser.add_argument("--region")
    parser.add_argument("--tag")
    parser.add_argument("--manifest", type=Path, required=True, help="Archivo nuevo, preferiblemente fuera del checkout")
    parser.add_argument("--reuse-manifest", type=Path, help="Evidencia existente revisada y aprobada")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        tag = validate_source(args.tag)
        env = dict(os.environ) if args.from_environment else parse_env(args.env_file or ROOT / f".env.{args.environment}")
        region = args.region or env.get("AWS_REGION") or "us-east-1"
        require(bool(re.fullmatch(r"\d{12}", args.account)) and bool(re.fullmatch(r"[a-z0-9-]+", region)), "Cuenta/región inválidas")
        options = builds(env)
        approved = json.loads(args.reuse_manifest.read_text()) if args.reuse_manifest else None
        publish(args.environment, args.account, region, tag, options, args.manifest, approved)
        return 0
    except (PrecondicionError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, PrecondicionError) else type(error).__name__
        print(f"Publicación detenida: {message}. Conservar evidencia parcial y reconciliar antes de reintentar.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
