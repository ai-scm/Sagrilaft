"""
El CI solo revisa código: no entra a AWS, no publica imágenes y no despliega.

Contexto: hasta noviembre de 2026 el CI publicaba imágenes en ECR de producción con un
rol OIDC compartido por toda la organización y con permisos de más, y comparaba la
infraestructura contra staging. Publicar y desplegar se hacen a mano, así que esos pasos
solo sumaban accesos y un CI en rojo. Estas pruebas evitan que vuelvan sin una decisión.

También comprueban que el rol preparado para automatizar staging en el futuro
(infra/sagrilaft/policies/github-staging/) siga limitado a staging.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
POLITICAS_STAGING = ROOT / "infra" / "sagrilaft" / "policies" / "github-staging"


def _sin_comentarios(texto: str) -> str:
    return "\n".join(linea for linea in texto.splitlines() if not linea.strip().startswith("#"))


def _workflows() -> dict[str, str]:
    return {p.name: _sin_comentarios(p.read_text()) for p in sorted(WORKFLOWS.glob("*.y*ml"))}


def test_solo_existe_el_workflow_de_ci():
    assert list(_workflows()) == ["ci.yml"]


def test_ci_no_puede_pedir_credenciales_ni_usar_secretos():
    for nombre, texto in _workflows().items():
        assert "id-token" not in texto, nombre
        assert "configure-aws-credentials" not in texto, nombre
        assert "secrets." not in texto, nombre
        assert "vars." not in texto, nombre
        assert re.search(r"^permissions:\s*\n\s+contents: read\s*$", texto, re.M), nombre


def test_ci_no_publica_ni_despliega():
    texto = _workflows()["ci.yml"]
    for prohibido in ("build_and_push_ecr_images", "deploy_release", "run_ecs_migration",
                      "cdk deploy", "deploy:", "cdk diff", "diff:", "docker push", "aws "):
        assert prohibido not in texto, prohibido


def test_ci_cubre_backend_frontend_infraestructura_y_secretos():
    texto = _workflows()["ci.yml"]
    for requerido in (
        "gitleaks",
        "python -m pytest",
        "validate_envs.py",
        "pip-audit",
        "npm --prefix apps/formulario-publico test",
        "build:publico",
        "build:portal",
        "tsc --noEmit",
        "node --test",
        "synth:staging -- --no-lookups",
        "synth:prod -- --no-lookups",
    ):
        assert requerido in texto, requerido


def test_nombres_de_jobs_estables_para_la_proteccion_de_main():
    # Si cambian, hay que cambiar también los checks obligatorios de la rama main.
    nombres = re.findall(r"^    name: (.+)$", _workflows()["ci.yml"], re.M)
    assert nombres == ["Secretos (gitleaks)", "Backend", "Frontend", "Infraestructura"]


def test_rol_futuro_de_staging_solo_confia_en_el_ambiente_staging():
    politica = json.loads((POLITICAS_STAGING / "trust-policy.template.json").read_text())
    [declaracion] = politica["Statement"]
    condicion = declaracion["Condition"]
    assert "StringLike" not in condicion  # sin comodines
    assert condicion["StringEquals"]["token.actions.githubusercontent.com:sub"] == (
        "repo:ai-scm/Sagrilaft:environment:staging"
    )
    assert condicion["StringEquals"]["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"


def test_rol_futuro_de_staging_no_alcanza_produccion_ni_otros_servicios():
    politica = json.loads((POLITICAS_STAGING / "publicar-imagenes-policy.template.json").read_text())
    acciones, recursos = set(), []
    for declaracion in politica["Statement"]:
        assert declaracion["Effect"] == "Allow"
        acciones.update([declaracion["Action"]] if isinstance(declaracion["Action"], str) else declaracion["Action"])
        recursos += [declaracion["Resource"]] if isinstance(declaracion["Resource"], str) else declaracion["Resource"]

    assert all(a.startswith(("ecr:", "ssm:GetParameters")) for a in acciones), acciones
    assert not any("*" in a for a in acciones)
    # El único recurso "*" es el login de ECR, que AWS no permite acotar.
    assert recursos.count("*") == 1
    for recurso in (r for r in recursos if r != "*"):
        assert "sagrilaft-staging-" in recurso or "/sagrilaft/staging/" in recurso, recurso
        assert "prod" not in recurso, recurso


def test_ci_corre_en_los_pr_y_en_dev_y_main():
    # Flujo de ramas: feature/* y fix/* -> PR a dev -> PR de dev a main.
    texto = _workflows()["ci.yml"]
    assert re.search(r"^  pull_request:\s*$", texto, re.M)
    push = re.search(r"^  push:\n    branches:\n((?:      - .+\n)+)", texto, re.M)
    assert push
    ramas = [linea.split("-", 1)[1].split("#")[0].strip() for linea in push.group(1).splitlines()]
    assert ramas == ["dev", "main"]
