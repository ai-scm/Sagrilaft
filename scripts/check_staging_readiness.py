#!/usr/bin/env python3
"""Checks that can be completed before real domains/ACM are available.

This script intentionally does not validate DNS, ACM, deployed ECS state or AWS
secrets values. It verifies that the repository is ready to attempt staging once
images, secrets and domains are supplied.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_ACCOUNT = "874641912777"
BEDROCK_MODEL_ID = (
    "arn:aws:bedrock:us-east-1:874641912777:"
    "inference-profile/us.anthropic.claude-sonnet-4-6"
)
HOSTED_ZONE_ID = "Z10446292T6I6L9P7R8AQ"
EXPECTED_DOMAINS = {
    "forms-sagrilaft.ia.blend360.com",
    "sagrilaft.ia.blend360.com",
    "login-sagrilaft.ia.blend360.com",
    "forms-staging-sagrilaft.ia.blend360.com",
    "staging-sagrilaft.ia.blend360.com",
    "login-staging-sagrilaft.ia.blend360.com",
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def read_first_existing(paths: list[str]) -> tuple[str, str]:
    for path in paths:
        candidate = ROOT / path
        if candidate.exists():
            return path, candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(f"No existe ninguno de estos archivos: {', '.join(paths)}")


def file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def check_required_files() -> Check:
    required = [
        "backend/Dockerfile",
        "frontend/apps/formulario-publico/Dockerfile",
        "frontend/apps/portal-interno/Dockerfile",
        "keycloak/Dockerfile",
        "keycloak/realm-sagrilaft.json",
        "infra/sagrilaft/lib/constructs/ecs-fargate.ts",
        ".github/workflows/ci.yml",
    ]
    missing = [path for path in required if not file_exists(path)]
    return Check("required-files", not missing, f"missing={missing}" if missing else "all required files exist")


def check_no_instance_runtime() -> Check:
    patterns = [
        r"new\s+ec2\.Instance",
        r"CfnInstance",
        r"AutoScalingGroup",
        r"LaunchTemplate",
        r"UserData",
        r"docker-compose\.prod",
        r"\.env\.runtime",
        r"\.env\.aws",
    ]
    targets = ["infra/sagrilaft/lib", "PLAN.md", "docs"]
    hits: list[str] = []
    for target in targets:
        base = ROOT / target
        files = [base] if base.is_file() else base.rglob("*")
        for path in files:
            if not path.is_file() or "node_modules" in path.parts or "cdk.out" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                if re.search(pattern, text):
                    hits.append(f"{path.relative_to(ROOT)}:{pattern}")
    return Check("no-instance-runtime", not hits, f"hits={hits}" if hits else "no server instance runtime patterns found")


def check_phase1_cdk_contract() -> Check:
    app = read("infra/sagrilaft/bin/app.ts")
    stack = read("infra/sagrilaft/lib/sagrilaft-stack.ts")
    networking = read("infra/sagrilaft/lib/constructs/networking.ts")
    ecs = read("infra/sagrilaft/lib/constructs/ecs-fargate.ts")
    lb = read("infra/sagrilaft/lib/constructs/load-balancer.ts")
    constructs_dir = ROOT / "infra/sagrilaft/lib/constructs"

    required = {
        "construct compute.ts retirado": not (constructs_dir / "compute.ts").exists(),
        "construct observability.ts retirado": not (constructs_dir / "observability.ts").exists(),
        "staging/prod bloquean cuenta vieja": "TARGET_ACCOUNT" in app and "CDK_DEFAULT_ACCOUNT" in app and "No usar la cuenta anterior" in app,
        "stack instancia EcsFargate": "new EcsFargate" in stack,
        "stack no usa HostedZone.fromLookup": "HostedZone.fromLookup" not in stack,
        "stack soporta hostedZoneId explicito": "hostedZoneId" in stack and "fromHostedZoneAttributes" in stack,
        "networking define sgEcs": "public readonly sgEcs" in networking,
        "networking permite ALB hacia ECS 8080": "Port.tcp(8080)" in networking,
        "networking permite ALB hacia ECS 8000": "Port.tcp(8000)" in networking,
        "ECS usa FargateService": "new ecs.FargateService" in ecs,
        "ECS usa subnets privadas aisladas": "SubnetType.PRIVATE_ISOLATED" in ecs,
        "ECS usa target groups IP": "TargetType.IP" in ecs,
        "ECS define execution role": "TaskExecutionRole" in ecs,
        "ECS define task roles por servicio": all(item in ecs for item in ["FrontendTaskRole", "PortalTaskRole", "BackendTaskRole", "KeycloakTaskRole"]),
        "ECS define log groups por servicio": "LogGroup" in ecs and "/sagrilaft/${ambiente}/ecs/" in ecs,
        "ALB recibe target groups ECS": all(item in lb for item in ["targetFormularioPublico", "targetPortalInterno", "targetBackend", "targetKeycloak"]),
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "phase1-cdk-contract",
        not failed,
        "ECS/Fargate CDK contract complete" if not failed else f"failed={failed}",
    )


def check_image_tag_required() -> Check:
    stack = read("infra/sagrilaft/lib/sagrilaft-stack.ts")
    package = read("infra/sagrilaft/package.json")
    ok = (
        "requiere -c imageTag=<commit-sha>" in stack
        and "imageTag || 'dev'" in stack
        and "deploy:staging:bootstrap" in package
        and "-c desiredCount=0" in package
    )
    return Check("image-tag-required", ok, "staging/prod require explicit imageTag" if ok else "imageTag guard not found")


def check_bootstrap_desired_count() -> Check:
    stack = read("infra/sagrilaft/lib/sagrilaft-stack.ts")
    ecs = read("infra/sagrilaft/lib/constructs/ecs-fargate.ts")
    package = read("infra/sagrilaft/package.json")
    required = {
        "stack lee desiredCount": "tryGetContext('desiredCount')" in stack and "Number.parseInt" in stack,
        "stack valida desiredCount": "desiredCount invalido" in stack,
        "stack pasa desiredCount a ECS": "desiredCount," in stack,
        "ECS propaga desiredCount": "readonly desiredCount: number" in ecs and "props.desiredCount" in ecs,
        "scripts bootstrap staging/prod": "deploy:staging:bootstrap" in package and "deploy:prod:bootstrap" in package,
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "bootstrap-desired-count",
        not failed,
        "bootstrap deploy can create infra with ECS services at desiredCount=0" if not failed else f"failed={failed}",
    )


def check_migration_task() -> Check:
    ecs = read("infra/sagrilaft/lib/constructs/ecs-fargate.ts")
    entrypoint = read("backend/entrypoint.sh")
    stack = read("infra/sagrilaft/lib/sagrilaft-stack.ts")
    required = [
        "MigrationTaskDefinition" in ecs,
        "RUN_MODE: 'migrate'" in ecs,
        "MigrationLogGroup" in ecs,
        'RUN_MODE:-server' in entrypoint,
        "alembic upgrade head" in entrypoint,
        "EcsMigrationTaskDefinitionArn" in stack,
        "EcsMigrationLogGroupName" in stack,
    ]
    ok = all(required)
    return Check("migration-task", ok, "migration task and outputs configured" if ok else "migration task wiring incomplete")


def check_keycloak_build_args() -> Check:
    dockerfile = read("keycloak/Dockerfile")
    workflow = read(".github/workflows/ci.yml")
    ok = all(
        item in dockerfile
        for item in ["ARG KEYCLOAK_PORTAL_URL", "ARG KEYCLOAK_FORMULARIO_URL", "realm-sagrilaft.template.json"]
    ) and all(
        item in workflow
        for item in ["KEYCLOAK_PORTAL_URL", "KEYCLOAK_FORMULARIO_URL"]
    )
    return Check("keycloak-build-args", ok, "Keycloak realm URLs are build-time parameters" if ok else "Keycloak build args missing")


def check_cdk_context() -> Check:
    context = json.loads(read("infra/sagrilaft/cdk.json")).get("context", {})
    required = ["environment", "region", "hostedZoneName", "hostedZoneId", "domainName", "portalDomainName", "keycloakDomainName"]
    missing = [key for key in required if key not in context]
    return Check("cdk-context", not missing, f"missing={missing}" if missing else "required context keys exist")


def check_phase0_env_contract() -> Check:
    required = [
        "STORAGE_BACKEND=s3",
        "S3_BUCKET=",
        "SECRET_KEY=",
        "BEDROCK_MODEL_ID=",
        "KEYCLOAK_ISSUER_URL=https://",
        "VITE_KEYCLOAK_URL=https://",
        "VITE_RAZON_SOCIAL=HIGH TECH SOFTWARE S.A.S",
        "VITE_CORREO_DATOS=administrativocol@blend360.com",
        "ZOHO_REDIRECT_URI=https://",
        "ZOHO_WEBHOOK_SIGNATURE_HEADER=X-ZS-WEBHOOK-SIGNATURE",
    ]
    forbidden = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "STORAGE_BACKEND=local"]
    staging_path, staging_content = read_first_existing([".env.staging.example", ".env.staging"])
    prod_path, prod_content = read_first_existing([".env.prod.example", ".env.prod"])
    files = {
        staging_path: staging_content,
        prod_path: prod_content,
    }
    missing_hits = [
        f"{path}:{item}"
        for path, content in files.items()
        for item in required
        if item not in content
    ]
    forbidden_hits = [
        f"{path}:{item}"
        for path, content in files.items()
        for item in forbidden
        if item in content
    ]
    ok = not missing_hits and not forbidden_hits
    detail = (
        "staging/prod env examples enforce ECS/S3 contract"
        if ok
        else f"missing={missing_hits} forbidden={forbidden_hits}"
    )
    return Check("phase0-env-contract", ok, detail)


def check_zoho_real_staging_contract() -> Check:
    _, staging_env = read_first_existing([".env.staging.example", ".env.staging"])
    _, prod_env = read_first_existing([".env.prod.example", ".env.prod"])
    config_params = read("infra/sagrilaft/lib/constructs/config-parameters.ts")

    required = {
        "staging usa Zoho real": "ZOHO_SIGN_TESTING=false" in staging_env,
        "prod usa Zoho real": "ZOHO_SIGN_TESTING=false" in prod_env,
        "staging tiene redirect uri": "ZOHO_REDIRECT_URI=https://staging-sagrilaft.ia.blend360.com/oauth/zoho/callback" in staging_env,
        "prod tiene redirect uri": "ZOHO_REDIRECT_URI=https://sagrilaft.ia.blend360.com/oauth/zoho/callback" in prod_env,
        "CDK configura staging/prod con Zoho real": "['staging', 'prod'].includes(props.ambiente) ? 'false' : 'true'" in config_params,
        "CDK publica redirect uri": "ZOHO_REDIRECT_URI" in config_params and "/oauth/zoho/callback" in config_params,
        "CDK publica header HMAC": "ZOHO_WEBHOOK_SIGNATURE_HEADER" in config_params and "X-ZS-WEBHOOK-SIGNATURE" in config_params,
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "zoho-real-staging-contract",
        not failed,
        "staging/prod use real Zoho signing mode" if not failed else f"failed={failed}",
    )


def check_phase0_domain_contract() -> Check:
    files = {
        read_first_existing([".env.staging.example", ".env.staging"])[0]: read_first_existing([".env.staging.example", ".env.staging"])[1],
        read_first_existing([".env.prod.example", ".env.prod"])[0]: read_first_existing([".env.prod.example", ".env.prod"])[1],
        "infra/sagrilaft/package.json": read("infra/sagrilaft/package.json"),
        "infra/sagrilaft/cdk.json": read("infra/sagrilaft/cdk.json"),
    }
    all_text = "\n".join(files.values())
    missing_domains = sorted(domain for domain in EXPECTED_DOMAINS if domain not in all_text)
    hosted_zone_missing = [
        path for path, content in files.items()
        if path in {"infra/sagrilaft/package.json", "infra/sagrilaft/cdk.json"} and HOSTED_ZONE_ID not in content
    ]
    ok = not missing_domains and not hosted_zone_missing
    detail = (
        "domain and hosted zone contract configured"
        if ok
        else f"missing-domains={missing_domains} hosted-zone-missing={hosted_zone_missing}"
    )
    return Check("phase0-domain-contract", ok, detail)


def check_bedrock_target_account() -> Check:
    files = {
        read_first_existing([".env.staging.example", ".env.staging"])[0]: read_first_existing([".env.staging.example", ".env.staging"])[1],
        read_first_existing([".env.prod.example", ".env.prod"])[0]: read_first_existing([".env.prod.example", ".env.prod"])[1],
        "infra/sagrilaft/package.json": read("infra/sagrilaft/package.json"),
        "infra/sagrilaft/lib/deployment-constants.ts": read("infra/sagrilaft/lib/deployment-constants.ts"),
    }
    missing = [path for path, content in files.items() if BEDROCK_MODEL_ID not in content]
    ok = not missing
    detail = (
        "Bedrock inference profile configured for target account"
        if ok
        else f"missing={missing}"
    )
    return Check("bedrock-target-account", ok, detail)


def check_frontend_api_contract() -> Check:
    shared_client = read("frontend/shared/services/apiClient.js")
    public_app = read("frontend/apps/formulario-publico/src/App.jsx")
    public_nginx = read("frontend/apps/formulario-publico/nginx.conf")
    portal_nginx = read("frontend/apps/portal-interno/nginx.conf")
    lb = read("infra/sagrilaft/lib/constructs/load-balancer.ts")
    _, staging_env = read_first_existing([".env.staging.example", ".env.staging"])
    _, prod_env = read_first_existing([".env.prod.example", ".env.prod"])

    required = {
        "frontend usa /api relativo": "API_BASE = '/api'" in shared_client,
        "descarga publica usa /api relativo": 'href={`/api/formularios/${codigoPeticion}/pdf`}' in read("frontend/apps/formulario-publico/src/components/SubmittedView.jsx"),
        "formulario solo usa VITE_PORTAL_INTERNO_URL para redireccion": "VITE_PORTAL_INTERNO_URL" in public_app,
        "nginx formulario mantiene fallback interno /api": "location /api/" in public_nginx and "proxy_pass         http://backend:8000;" in public_nginx,
        "nginx portal mantiene fallback interno /api": "location /api/" in portal_nginx and "proxy_pass         http://backend:8000;" in portal_nginx,
        "ALB enruta /api formulario antes del frontend": "BackendApiPublica" in lb and "priority: 1" in lb and "pathPatterns(['/api/*', '/health'])" in lb,
        "ALB enruta /api portal antes del frontend": "BackendApiPortal" in lb and "priority: 2" in lb and "pathPatterns(['/api/*', '/health'])" in lb,
        "staging deja VITE_BACKEND_URL vacio": re.search(r"(?m)^VITE_BACKEND_URL=$", staging_env) is not None,
        "prod deja VITE_BACKEND_URL vacio": re.search(r"(?m)^VITE_BACKEND_URL=$", prod_env) is not None,
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "frontend-api-contract",
        not failed,
        "frontends use relative /api and ALB routes API to backend" if not failed else f"failed={failed}",
    )


def check_zoho_webhook_hmac_contract() -> Check:
    router = read("backend/api/routers/webhooks.py")
    config = read("backend/infrastructure/configuracion.py")
    service = read("backend/services/firma/firma_service.py")

    required = {
        "router lee cuerpo crudo": "await request.body()" in router,
        "router valida hmac sha256": "hmac.new" in router and "hashlib.sha256" in router,
        "router soporta firma hex/base64": "base64.b64encode" in router and "digest.hex()" in router,
        "router usa header configurable": "webhook_signature_header" in router,
        "config expone header HMAC": "ZOHO_WEBHOOK_SIGNATURE_HEADER" in config,
        "servicio procesa webhook verificado": "procesar_webhook_verificado" in service,
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "zoho-webhook-hmac-contract",
        not failed,
        "Zoho webhooks require HMAC SHA-256 signature validation" if not failed else f"failed={failed}",
    )


def check_frontend_legal_build_args() -> Check:
    dockerfile = read("frontend/apps/formulario-publico/Dockerfile")
    build_script = read("scripts/build_and_push_ecr_images.py")
    workflow = read(".github/workflows/ci.yml")

    required = {
        "Dockerfile recibe VITE_RAZON_SOCIAL": "ARG VITE_RAZON_SOCIAL" in dockerfile and "ENV VITE_RAZON_SOCIAL=" in dockerfile,
        "Dockerfile recibe VITE_CORREO_DATOS": "ARG VITE_CORREO_DATOS" in dockerfile and "ENV VITE_CORREO_DATOS=" in dockerfile,
        "script local pasa razon social": "VITE_RAZON_SOCIAL" in build_script,
        "script local pasa correo datos": "VITE_CORREO_DATOS" in build_script,
        "CI pasa razon social": "vars.VITE_RAZON_SOCIAL" in workflow,
        "CI pasa correo datos": "vars.VITE_CORREO_DATOS" in workflow,
    }
    failed = [name for name, ok in required.items() if not ok]
    return Check(
        "frontend-legal-build-args",
        not failed,
        "legal frontend values are passed at image build time" if not failed else f"failed={failed}",
    )


def main() -> int:
    checks = [
        check_required_files(),
        check_no_instance_runtime(),
        check_phase1_cdk_contract(),
        check_image_tag_required(),
        check_bootstrap_desired_count(),
        check_migration_task(),
        check_keycloak_build_args(),
        check_cdk_context(),
        check_phase0_env_contract(),
        check_zoho_real_staging_contract(),
        check_phase0_domain_contract(),
        check_bedrock_target_account(),
        check_zoho_webhook_hmac_contract(),
        check_frontend_api_contract(),
        check_frontend_legal_build_args(),
    ]

    failed = [check for check in checks if not check.ok]
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")

    if failed:
        print("\nStaging readiness incomplete.")
        return 1

    print("\nStaging readiness checks passed. Pending external items: DNS/Route 53, ECR images, AWS secrets and deploy validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
