#!/usr/bin/env python3
"""Preparar -> migrar -> verificar evidencia -> activar -> smoke.

Sin --execute solo consulta AWS y sintetiza localmente, sin mutaciones AWS.
Excepción: --close-manual sin --execute revisa únicamente evidencia local.
Modo manual (staging): salida 3 tras activar, lock retenido hasta cierre autorizado.
Requiere stack existente: modo compatible, o bootstrap ya creado con cero tareas.
No construye imágenes, no crea el bootstrap ni hace rollback automático.

Plan JSON (sin secretos): environment, account, region, mode (compatible/bootstrap),
previous_tag, candidate_tag (SHA Git completo), desired_count, expected_head,
previous_revisions (lista), digests (backend/formulario-publico/portal-interno/keycloak),
context (contexto CDK completo), smoke_command (lista de argumentos ejecutables).
Alternativa staging: smoke_mode=manual, smoke_command=[], manual_checks definidos.
context incluye dominios, zona, certificado, Bedrock, flags Zoho/listas/NAT y SNS.
Los tags candidatos deben existir en repositorios IMMUTABLE sin exclusiones.

El bloqueo compartido usa S3Bucket del stack, clave _deployment/<stack>.lock.
Requiere permisos S3 condicionales (PutObject/GetObject/DeleteObject), además de
lecturas ECS/ECR/SSM/CloudFormation/Logs y permisos del deploy y lanzador.
Ante cualquier fallo después de adquirirlo, se conserva. Reconciliar stack,
taskArn y evidencias antes de retirar manualmente el bloqueo. No tiene TTL.
Todos los operadores deben respetarlo; CDK directo puede saltárselo.
"""
import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tempfile
import uuid

from run_ecs_migration import MigrationError, run_migration

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra/sagrilaft"
SERVICES = {"backend": "EcsBackendServiceName", "formulario-publico": "EcsFrontendServiceName",
            "portal-interno": "EcsPortalServiceName", "keycloak": "EcsKeycloakServiceName"}
REPOS = {"backend": "EcrBackendUri", "formulario-publico": "EcrFormularioPublicoUri",
         "portal-interno": "EcrPortalInternoUri", "keycloak": "EcrKeycloakUri"}


def require(ok, message):
    if not ok:
        raise MigrationError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


MANUAL_CHECKS = ("release_sha", "crear_y_leer_correo", "guardar_y_recuperar", "borrador_con_correo")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_plan(p):
    p20 = bool(re.fullmatch(r"p20-[a-f0-9]{12}", p.get("environment", "")))
    require(p["environment"] in ("staging", "prod") or p20, "Ambiente inválido")
    require(p["mode"] in ("compatible", "bootstrap"), "Cambio incompatible: necesita un plan de mantenimiento separado")
    require(bool(re.fullmatch(r"\d{12}", p["account"])), "Cuenta inválida")
    require(bool(re.fullmatch(r"[a-z0-9-]+", p["region"])), "Región inválida")
    require(bool(re.fullmatch(r"[a-f0-9]{40}", p["candidate_tag"])), "Candidato debe ser SHA completo")
    require(bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", p["previous_tag"])), "Tag anterior inválido")
    require(p["previous_tag"] != p["candidate_tag"], "Candidato debe diferir de la release anterior")
    if p["mode"] == "compatible":
        require(p["previous_tag"] not in ("latest", "bootstrap-placeholder", "synth-placeholder"), "Release anterior no válida para actualización compatible")
    require(type(p["desired_count"]) is int and p["desired_count"] > 0, "Capacidad inválida")
    require(bool(re.fullmatch(r"[A-Za-z0-9_]+", p["expected_head"])), "Head inválido")
    require(isinstance(p["previous_revisions"], list) and len(p["previous_revisions"]) <= 1
            and all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_]+", x) for x in p["previous_revisions"]), "Revisiones previas inválidas")
    require(set(p["digests"]) == set(SERVICES), "Faltan digests de las cuatro imágenes")
    require(all(re.fullmatch(r"sha256:[a-f0-9]{64}", x) for x in p["digests"].values()), "Digest inválido")
    smoke_mode = p.get("smoke_mode", "automatic")
    require(smoke_mode in ("automatic", "manual"), "Modalidad smoke inválida")
    if smoke_mode == "manual":
        require(p["environment"] == "staging", "Validación manual solo habilitada en staging")
        require(p.get("smoke_command") == [], "Modo manual no admite comando smoke")
        require(p.get("manual_checks") == list(MANUAL_CHECKS), "Faltan comprobaciones manuales")
    else:
        require(isinstance(p["smoke_command"], list) and p["smoke_command"]
                and all(isinstance(x, str) and x for x in p["smoke_command"]), "Falta comando smoke aprobado")
    reserved = {"environment", "account", "region", "imageTag", "migrationImageTag", "desiredCount", "p20AllowActivation"}
    require(not reserved.intersection(p["context"]), "Contexto no puede sobrescribir ambiente/tags/capacidad")
    required_context = {"hostedZoneName", "hostedZoneId", "domainName", "portalDomainName",
                        "keycloakDomainName", "certificateArn", "bedrockModelId", "zohoSecretYaExiste",
                        "proveedorListasCautela", "habilitarNatEgress", "snsAlertasSub"}
    require(required_context.issubset(p["context"]), "Falta contexto CDK explícito del ambiente")
    require(all(isinstance(v, (str, bool, int)) for v in p["context"].values()), "Contexto debe contener valores escalares")
    operation = p.get("p20_operation")
    if operation is not None:
        require(p20 and operation in ("rollback-services", "connect-restored-db", "activate-previous"),
                "Operación P20 inválida o fuera del ambiente aislado")
        require(p["mode"] == "compatible", "La operación P20 requiere un stack aislado ya preparado")
        if operation in ("rollback-services", "activate-previous"):
            require(set(p.get("previous_digests", {})) == set(SERVICES), "Rollback requiere digests previos de los cuatro servicios")
            require(all(re.fullmatch(r"sha256:[a-f0-9]{64}", x) for x in p["previous_digests"].values()), "Digest previo inválido")
        if operation == "connect-restored-db":
            require(bool(p["context"].get("databaseHostOverride")), "La conexión requiere host de RDS restaurada")
            require(bool(re.fullmatch(r"p20-[a-f0-9]{12}-restore-[a-z0-9-]{1,32}",
                                      p["context"].get("restoredDbIdentifier", ""))),
                    "La conexión requiere identificador de RDS restaurada etiquetado para P20")
    if p20:
        require(p["mode"] in ("bootstrap", "compatible"), "P20 solo admite bootstrap aislado o actualización compatible")
        require(p["context"].get("hostedZoneName") == "" and p["context"].get("hostedZoneId") == "",
                "P20 no puede usar Hosted Zone ni crear DNS público")
        require(p["context"].get("snsAlertasSub") == "", "P20 no admite suscripciones SNS de correo")
        require(p["context"].get("habilitarNatEgress") is False, "P20 requiere egreso NAT deshabilitado")
        require(p["context"].get("proveedorListasCautela") in ("dummy", "deshabilitado"), "P20 requiere proveedor de listas simulado/deshabilitado")
        require(p["context"].get("zohoSecretYaExiste") is False, "P20 no puede importar secretos externos compartidos")
        require(not p["context"].get("sesEmailOrigen"), "P20 no admite correo SES de salida")
        db_override = p["context"].get("databaseHostOverride", "")
        require(isinstance(db_override, str) and (not db_override or bool(re.fullmatch(r"[A-Za-z0-9.-]+", db_override))),
                "Host de BD restaurada inválido")
        fault = p.get("p20_migration_fault")
        require(fault in (None, "fail-before-ddl", "observer-loss-after-launch"),
                "Modo de fallo de migración P20 inválido")
        if fault:
            require(p["mode"] == "compatible" and operation is None,
                    "Fault injection requiere el flujo coordinado compatible P20")
    else:
        require("p20_migration_fault" not in p, "Fault injection solo se permite en P20")


def strip_metadata(value):
    if isinstance(value, dict):
        return {k: strip_metadata(v) for k, v in value.items()
                if k != "Metadata" and not (isinstance(v, dict) and v.get("Type") == "AWS::CDK::Metadata")}
    if isinstance(value, list):
        return [strip_metadata(v) for v in value]
    return value


# Excepción aprobada para staging: ocho rutas y pares completos, no reglas Unicode.
# Solo afecta a copias de comparación; nunca a assemblies ni recursos AWS.
STAGING_UNICODE_PAIRS = (
    (('Resources', 'EcrBackendRepo0C255C53', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'), '{"rules":[{"rulePriority":1,"description":"Mantener las últimas 30 imágenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}', '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrFormularioPublicoRepo71B2173B', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'), '{"rules":[{"rulePriority":1,"description":"Mantener las últimas 30 imágenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}', '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrPortalInternoRepo64131791', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'), '{"rules":[{"rulePriority":1,"description":"Mantener las últimas 30 imágenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}', '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrKeycloakRepoD812844A', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'), '{"rules":[{"rulePriority":1,"description":"Mantener las últimas 30 imágenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}', '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'AlarmasCriticasAlarmaErroresServidor05DAF4B7', 'Properties', 'AlarmDescription'), 'Alarma Crítica: Se detectaron más de 5 errores HTTP 5xx en el servidor backend durante los últimos 5 minutos.', 'Alarma Cr?tica: Se detectaron m?s de 5 errores HTTP 5xx en el servidor backend durante los ?ltimos 5 minutos.'),
    (('Resources', 'AlarmasCriticasAlarmaSaturacionCpu3C8591DA', 'Properties', 'AlarmDescription'), 'Alarma de Rendimiento: El uso de CPU del servicio Backend superó el 85% de su capacidad.', 'Alarma de Rendimiento: El uso de CPU del servicio Backend super? el 85% de su capacidad.'),
    (('Resources', 'AlarmasCriticasAlarmaSaturacionMemoria42793BCD', 'Properties', 'AlarmDescription'), 'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend superó el 85% de su capacidad.', 'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend super? el 85% de su capacidad.'),
    (('Resources', 'DashboardNegocio53ADAF63', 'Properties', 'DashboardBody', 'Fn::Join', 1, 0), '{"widgets":[{"type":"metric","width":24,"height":6,"x":0,"y":0,"properties":{"view":"bar","title":"Tasas de Éxito: Decisiones de Expedientes","region":"', '{"widgets":[{"type":"metric","width":24,"height":6,"x":0,"y":0,"properties":{"view":"bar","title":"Tasas de ?xito: Decisiones de Expedientes","region":"'),
)

# El template histórico P20 contiene exactamente estos textos descriptivos con
# sustituciones `?`. Solo se equiparan con la versión ASCII aprobada y solo en
# P20; una diferencia en cualquier otro path/valor continúa bloqueando.
P20_ASCII_PAIRS = (
    (('Resources', 'EcrBackendRepo0C255C53', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'),
     '{"rules":[{"rulePriority":1,"description":"Mantener las ultimas 30 imagenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}',
     '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrFormularioPublicoRepo71B2173B', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'),
     '{"rules":[{"rulePriority":1,"description":"Mantener las ultimas 30 imagenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}',
     '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrKeycloakRepoD812844A', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'),
     '{"rules":[{"rulePriority":1,"description":"Mantener las ultimas 30 imagenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}',
     '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'EcrPortalInternoRepo64131791', 'Properties', 'LifecyclePolicy', 'LifecyclePolicyText'),
     '{"rules":[{"rulePriority":1,"description":"Mantener las ultimas 30 imagenes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}',
     '{"rules":[{"rulePriority":1,"description":"Mantener las ?ltimas 30 im?genes para ahorrar costos","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":30},"action":{"type":"expire"}}]}'),
    (('Resources', 'AlarmasCriticasAlarmaErroresServidor05DAF4B7', 'Properties', 'AlarmDescription'),
     'Alarma Critica: Se detectaron mas de 5 errores HTTP 5xx en el servidor backend durante los ultimos 5 minutos.',
     'Alarma Cr?tica: Se detectaron m?s de 5 errores HTTP 5xx en el servidor backend durante los ?ltimos 5 minutos.'),
    (('Resources', 'AlarmasCriticasAlarmaSaturacionCpu3C8591DA', 'Properties', 'AlarmDescription'),
     'Alarma de Rendimiento: El uso de CPU del servicio Backend supero el 85% de su capacidad.',
     'Alarma de Rendimiento: El uso de CPU del servicio Backend super? el 85% de su capacidad.'),
    (('Resources', 'AlarmasCriticasAlarmaSaturacionMemoria42793BCD', 'Properties', 'AlarmDescription'),
     'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend supero el 85% de su capacidad.',
     'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend super? el 85% de su capacidad.'),
    (('Resources', 'DashboardNegocio53ADAF63', 'Properties', 'DashboardBody', 'Fn::Join', 1, 0),
     'Tasas de Exito: Decisiones de Expedientes',
     'Tasas de ?xito: Decisiones de Expedientes'),
    (('Outputs', 'AlbDns', 'Description'),
     'DNS privado del ALB interno P20; no crear DNS publico',
     'DNS privado del ALB interno P20; no crear DNS p?blico'),
    (('Outputs', 'EcsDatabaseHost', 'Description'),
     'Host de BD usado por tareas ECS; en P20 puede apuntar a una restauracion aislada',
     'Host de BD usado por tareas ECS; en P20 puede apuntar a una restauraci?n aislada'),
)


def comparison_template(value, environment=None, *, preserve_metadata=False):
    """Equivalencias exactas, conservando el criterio de metadata de cada comprobación."""
    result = copy.deepcopy(value if preserve_metadata else strip_metadata(value))
    if environment == "staging":
        pairs = STAGING_UNICODE_PAIRS
    elif re.fullmatch(r"p20-[a-f0-9]{12}", environment or ""):
        pairs = P20_ASCII_PAIRS
    else:
        return result
    for path, expected, observed in pairs:
        cursor = result
        try:
            for key in path[:-1]:
                cursor = cursor[key]
            value_at_path = cursor[path[-1]]
            if value_at_path == observed:
                cursor[path[-1]] = expected
            elif isinstance(value_at_path, str) and isinstance(observed, str) and value_at_path.count(observed) == 1:
                # Para DashboardBody solo se normaliza el título conocido; el
                # resto del documento JSON embebido se compara byte por byte.
                cursor[path[-1]] = value_at_path.replace(observed, expected, 1)
        except (KeyError, IndexError, TypeError):
            # Una ruta ausente/cambiada no se repara; la comparación seguirá fallando.
            continue
    return result


def assert_transition(before, after, phase, bootstrap=False, environment=None):
    """Rechaza cambios fuera de imagen/SHA; bootstrap admite capacidad/autoscaling."""
    before = comparison_template(before, environment)
    normalized = comparison_template(after, environment)
    previous = before["Resources"]
    resources = normalized["Resources"]
    allowed_scaling = {"AWS::ApplicationAutoScaling::ScalableTarget", "AWS::ApplicationAutoScaling::ScalingPolicy"}
    for key in set(previous) | set(resources):
        old, new = previous.get(key), resources.get(key)
        if old == new:
            continue
        if phase == "activate" and bootstrap and old is None and new["Type"] in allowed_scaling:
            del resources[key]
            continue
        require(old is not None and new is not None and old["Type"] == new["Type"], f"Cambio de recurso no permitido: {key}")
        kind = new["Type"]
        if kind == "AWS::ECS::TaskDefinition":
            old_containers = old["Properties"]["ContainerDefinitions"]
            containers = new["Properties"]["ContainerDefinitions"]
            require(len(containers) == len(old_containers) == 1, "Task definition inesperada")
            is_migration = containers[0]["Name"] == "migration"
            require(is_migration == (phase == "prepare"), f"Task definition fuera de fase: {key}")
            containers[0]["Image"] = old_containers[0]["Image"]
            old_env = {item["Name"]: item["Value"] for item in old_containers[0].get("Environment", [])}
            for item in containers[0].get("Environment", []):
                if item["Name"] == "GIT_SHA":
                    require("GIT_SHA" in old_env, "Falta SHA anterior")
                    item["Value"] = old_env["GIT_SHA"]
        elif phase == "activate" and bootstrap and kind == "AWS::ECS::Service":
            new["Properties"]["DesiredCount"] = old["Properties"]["DesiredCount"]
        else:
            raise MigrationError(f"Cambio ajeno a la release: {key}")
    for key in ("EcsMigrationImageTag", "EcsDesiredCount"):
        if (phase == "prepare" and key == "EcsMigrationImageTag") or (phase == "activate" and bootstrap and key == "EcsDesiredCount"):
            if key in before.get("Outputs", {}):
                normalized["Outputs"][key] = before["Outputs"][key]
            else:
                normalized.get("Outputs", {}).pop(key, None)
    require(strip_metadata(normalized) == strip_metadata(before), "Diff fuera del alcance de la fase")


@contextmanager
def environment(values):
    original = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def atomic_write(path, content):
    """Reemplazo POSIX en el mismo filesystem; nunca truncar el archivo vigente."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


ORCHESTRATOR_SOURCES = ("scripts/deploy_release.py", "scripts/deploy_release.sh",
                        "scripts/run_ecs_migration.py")


def record_orchestrator(rt, label="orchestrator", root=ROOT):
    """Commit base más snapshot exacto; un checkout modificado no se presenta como HEAD puro."""
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True, timeout=10).strip()
    commit = git("rev-parse", "HEAD")
    require(bool(re.fullmatch(r"[a-f0-9]{40}", commit)), "No se puede identificar el commit del orquestador")
    status = git("status", "--porcelain", "--untracked-files=normal")
    source_status = git("status", "--porcelain", "--", *ORCHESTRATOR_SOURCES)
    snapshot = rt.directory / (label + "-sources")
    snapshot.mkdir(mode=0o700, exist_ok=False)
    hashes = {}
    for name in ORCHESTRATOR_SOURCES:
        content = (root / name).read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        atomic_write(snapshot / Path(name).name, content.decode("utf-8"))
    rt.save(label + ".json", {
        "recordedAt": utc_now(), "baseCommit": commit,
        "checkoutDirty": bool(status), "orchestratorModified": bool(source_status),
        "sourceSha256": hashes, "sourceFingerprint": fingerprint(hashes),
        "snapshotDirectory": snapshot.name, "candidateTag": rt.plan["candidate_tag"],
        "note": "baseCommit no identifica por sí solo código modificado; usar snapshot y hashes"})


class Runtime:
    def __init__(self, plan, directory):
        self.plan, self.directory = plan, directory
        self.stack = "SagrilaftStack-" + plan["environment"]

    def aws(self, service, operation, *args):
        try:
            result = subprocess.run(["aws", service, operation, *args, "--region", self.plan["region"],
                                     "--output", "json", "--no-cli-pager", "--cli-connect-timeout", "10",
                                     "--cli-read-timeout", "30"], capture_output=True, text=True, timeout=45, check=True)
            value = json.loads(result.stdout or "{}")
            require(isinstance(value, dict), "Respuesta AWS inválida")
            return value
        except (OSError, ValueError, subprocess.SubprocessError):
            raise MigrationError(f"{service}/{operation}: fallo o resultado incierto; revisar evidencia") from None

    def save(self, name, value):
        atomic_write(self.directory / name, json.dumps(value, indent=2) + "\n")

    def event(self, value):
        path = self.directory / "events.jsonl"
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        atomic_write(path, previous + json.dumps(value) + "\n")
        print(json.dumps(value), flush=True)

    def synth(self, phase, image_tag, migration_tag, count):
        path = self.directory / phase
        context = {**self.plan["context"], "environment": self.plan["environment"],
                   "account": self.plan["account"], "region": self.plan["region"],
                   "imageTag": image_tag, "migrationImageTag": migration_tag, "desiredCount": count}
        if re.fullmatch(r"p20-[a-f0-9]{12}", self.plan["environment"]):
            context["p20AllowActivation"] = "true"
        args = [str(INFRA / "node_modules/.bin/cdk"), "synth", self.stack, "--output", str(path), "--lookups", "false"]
        for key, value in context.items():
            args += ["-c", f"{key}={str(value).lower() if isinstance(value, bool) else value}"]
        with (self.directory / f"{phase}.log").open("w") as log:
            subprocess.run(args, cwd=INFRA, stdout=log, stderr=log, check=True)
        return json.loads((path / f"{self.stack}.template.json").read_text())

    def deploy(self, phase):
        # Consumir la misma assembly inspeccionada, sin volver a sintetizar.
        self.event({"event": "deploy_started", "phase": phase})
        with (self.directory / f"{phase}-deploy.log").open("w") as log:
            subprocess.run([str(INFRA / "node_modules/.bin/cdk"), "deploy", self.stack,
                            "--app", str(self.directory / phase), "--require-approval", "never"],
                           cwd=INFRA, stdout=log, stderr=log, check=True)
        self.event({"event": "deploy_returned", "phase": phase})

    def smoke(self):
        with (self.directory / "smoke.log").open("w") as log:
            subprocess.run(self.plan["smoke_command"], cwd=ROOT, stdout=log, stderr=log, timeout=600, check=True)


def stack_state(rt):
    response = rt.aws("cloudformation", "describe-stacks", "--stack-name", rt.stack)
    require(len(response.get("Stacks", [])) == 1, "Stack ausente o ambiguo; ejecutar bootstrap por separado")
    stack = response["Stacks"][0]
    require(stack["StackStatus"] in ("CREATE_COMPLETE", "UPDATE_COMPLETE"), "Stack no está listo; reconciliar antes de continuar")
    expected = f"arn:aws:cloudformation:{rt.plan['region']}:{rt.plan['account']}:stack/{rt.stack}/"
    require(stack["StackId"].startswith(expected), "Stack de otra cuenta/región")
    return {entry["OutputKey"]: entry["OutputValue"] for entry in stack["Outputs"]}


def deployed_template(rt):
    body = rt.aws("cloudformation", "get-template", "--stack-name", rt.stack, "--template-stage", "Original")["TemplateBody"]
    return json.loads(body) if isinstance(body, str) else body


def services(rt, outputs, tag, count):
    response = rt.aws("ecs", "describe-services", "--cluster", outputs["EcsClusterName"], "--services",
                      *(outputs[key] for key in SERVICES.values()))
    require(not response.get("failures") and len(response.get("services", [])) == 4, "Faltan servicios ECS")
    require({s["serviceName"] for s in response["services"]} == {outputs[k] for k in SERVICES.values()}, "Servicios inesperados")
    for service in response["services"]:
        require(service["status"] == "ACTIVE" and service["pendingCount"] == 0
                and service["runningCount"] == service["desiredCount"], "Servicio no estable")
        require(service["desiredCount"] == 0 if count == 0 else service["desiredCount"] >= count, "Capacidad no corresponde al plan")
        deployments = service["deployments"]
        require(len(deployments) == 1 and deployments[0].get("rolloutState") == "COMPLETED", "Hay despliegue en curso o fallido")
        definition = rt.aws("ecs", "describe-task-definition", "--task-definition", service["taskDefinition"])["taskDefinition"]
        kind = next(k for k, v in SERVICES.items() if outputs[v] == service["serviceName"])
        require(definition["containerDefinitions"][0]["image"] == outputs[REPOS[kind]] + ":" + tag, "Servicio ejecuta una release distinta")
        arns = rt.aws("ecs", "list-tasks", "--cluster", outputs["EcsClusterName"],
                      "--service-name", service["serviceName"], "--desired-status", "RUNNING")["taskArns"]
        require(len(arns) == service["runningCount"], "Tareas cambiaron durante la comprobación")
        snapshot = []
        for offset in range(0, len(arns), 100):
            tasks = rt.aws("ecs", "describe-tasks", "--cluster", outputs["EcsClusterName"], "--tasks", *arns[offset:offset + 100])
            require(not tasks.get("failures") and len(tasks.get("tasks", [])) == len(arns[offset:offset + 100]), "No se pueden verificar todas las tareas")
            require({task["taskArn"] for task in tasks["tasks"]} == set(arns[offset:offset + 100]), "AWS devolvió otras tareas")
            for task in tasks["tasks"]:
                require(task["taskDefinitionArn"] == service["taskDefinition"] and task["lastStatus"] == "RUNNING", "Tarea de otra revisión o no activa")
                containers = task["containers"]
                require(len(containers) == 1 and containers[0]["image"] == outputs[REPOS[kind]] + ":" + tag
                        and bool(re.fullmatch(r"sha256:[a-f0-9]{64}", containers[0].get("imageDigest", ""))), "Imagen activa no verificable")
                if tag == rt.plan["candidate_tag"]:
                    require(containers[0]["imageDigest"] == rt.plan["digests"][kind], "Digest activo distinto del aprobado")
                snapshot.append({"taskArn": task["taskArn"], "taskDefinitionArn": task["taskDefinitionArn"],
                                 "image": containers[0]["image"], "imageDigest": containers[0]["imageDigest"]})
        service["verifiedTasks"] = snapshot
    return response["services"]


def verify_images(rt, outputs):
    for kind, output in REPOS.items():
        uri = outputs[output]
        prefix = f"{rt.plan['account']}.dkr.ecr.{rt.plan['region']}.amazonaws.com/"
        require(uri.startswith(prefix), "Repositorio de otra cuenta/región")
        repo = uri[len(prefix):]
        repositories = rt.aws("ecr", "describe-repositories", "--repository-names", repo)["repositories"]
        require(len(repositories) == 1 and repositories[0]["imageTagMutability"] == "IMMUTABLE", "Repo mutable: no se puede garantizar la imagen; resolver antes del deploy")
        images = rt.aws("ecr", "describe-images", "--repository-name", repo,
                        "--image-ids", f"imageTag={rt.plan['candidate_tag']}")["imageDetails"]
        require(len(images) == 1 and images[0]["imageDigest"] == rt.plan["digests"][kind], "Digest candidato distinto del aprobado")


def verify_tag_digests(rt, outputs, tag, digests):
    for kind, output in REPOS.items():
        uri = outputs[output]
        prefix = f"{rt.plan['account']}.dkr.ecr.{rt.plan['region']}.amazonaws.com/"
        require(uri.startswith(prefix), "Repositorio de otra cuenta/región")
        repo = uri[len(prefix):]
        repository = rt.aws("ecr", "describe-repositories", "--repository-names", repo)["repositories"]
        require(len(repository) == 1 and repository[0]["imageTagMutability"] == "IMMUTABLE",
                "Repositorio mutable: rollback no verificable")
        images = rt.aws("ecr", "describe-images", "--repository-name", repo,
                        "--image-ids", f"imageTag={tag}")["imageDetails"]
        require(len(images) == 1 and images[0]["imageDigest"] == digests[kind],
                f"Digest previo distinto del aprobado para {kind}")


def assert_service_rollback_transition(before, after, environment=None):
    """Permite solo cambiar task definitions y referencias de los 4 servicios ECS."""
    original = comparison_template(before, environment)
    target = comparison_template(after, environment)
    old_resources, new_resources = original["Resources"], target["Resources"]
    changed_task_defs = set()
    service_ids = set()
    for logical_id in set(old_resources) | set(new_resources):
        old, new = old_resources.get(logical_id), new_resources.get(logical_id)
        if old == new:
            continue
        require(old is not None and new is not None and old["Type"] == new["Type"],
                f"Rollback ECS alteraría recursos ajenos: {logical_id}")
        if old["Type"] == "AWS::ECS::TaskDefinition":
            old_props, new_props = copy.deepcopy(old["Properties"]), copy.deepcopy(new["Properties"])
            old_containers = old_props.get("ContainerDefinitions", [])
            new_containers = new_props.get("ContainerDefinitions", [])
            require(len(old_containers) == len(new_containers) == 1, "Task definition inesperada en rollback")
            require(old_containers[0].get("Name") != "migration", "Rollback de servicios no debe cambiar migración")
            old_containers[0]["Image"] = new_containers[0]["Image"] = "<release>"
            for container in (old_containers[0], new_containers[0]):
                for item in container.get("Environment", []):
                    if item.get("Name") == "GIT_SHA":
                        item["Value"] = "<release>"
            require(old_props == new_props, f"Rollback cambia configuración de task definition: {logical_id}")
            changed_task_defs.add(logical_id)
        elif old["Type"] == "AWS::ECS::Service":
            old_props, new_props = old["Properties"], new["Properties"]
            require(old_props.get("DesiredCount") == new_props.get("DesiredCount"),
                    f"Rollback no puede cambiar capacidad ECS: {logical_id}")
            old_fixed, new_fixed = copy.deepcopy(old_props), copy.deepcopy(new_props)
            old_fixed.pop("TaskDefinition", None)
            new_fixed.pop("TaskDefinition", None)
            require(old_fixed == new_fixed, f"Rollback cambia configuración del servicio: {logical_id}")
            service_ids.add(logical_id)
        else:
            raise MigrationError(f"Rollback ECS modificaría un recurso no permitido: {logical_id}")
    service_ids = {logical_id for logical_id, resource in new_resources.items()
                   if resource["Type"] == "AWS::ECS::Service"}
    require(len(changed_task_defs) == len(service_ids) == 4,
            "Rollback debe incluir cuatro task definitions de aplicación y cuatro servicios")
    for logical_id in service_ids:
        service = new_resources[logical_id]["Properties"]
        reference = service.get("TaskDefinition", {}).get("Ref")
        require(reference in changed_task_defs,
                f"Servicio no apunta a una de las task definitions revertidas: {logical_id}")
    require(original.get("Outputs") == target.get("Outputs"), "Rollback ECS cambia outputs del stack")


def assert_database_repoint_transition(before, after, host, desired_count, environment=None):
    """Permite BD restaurada y activar servicios P20 desde cero, sin migrar."""
    original = comparison_template(before, environment)
    target = comparison_template(after, environment)
    old_resources, new_resources = original["Resources"], target["Resources"]
    changed_containers = set()
    changed_services = set()
    for logical_id in set(old_resources) | set(new_resources):
        old, new = old_resources.get(logical_id), new_resources.get(logical_id)
        if old == new:
            continue
        require(old is not None and new is not None and old["Type"] == new["Type"],
                f"Reapuntar BD cambiaría recursos adicionales: {logical_id}")
        if old["Type"] == "AWS::ECS::Service":
            old_props, new_props = copy.deepcopy(old["Properties"]), copy.deepcopy(new["Properties"])
            require(old_props.get("DesiredCount") == 0 and new_props.get("DesiredCount") == desired_count,
                    f"P20 solo permite activar servicios desde cero a la capacidad planeada: {logical_id}")
            old_props.pop("DesiredCount", None)
            new_props.pop("DesiredCount", None)
            require(old_props == new_props, f"Reapuntar BD modifica otra configuración del servicio: {logical_id}")
            changed_services.add(logical_id)
            continue
        require(old["Type"] == "AWS::ECS::TaskDefinition",
                f"Reapuntar BD cambiaría un recurso ajeno a ECS: {logical_id}")
        old_props, new_props = copy.deepcopy(old["Properties"]), copy.deepcopy(new["Properties"])
        old_containers, new_containers = old_props.get("ContainerDefinitions", []), new_props.get("ContainerDefinitions", [])
        require(len(old_containers) == len(new_containers) == 1, "Task definition inesperada al reapuntar BD")
        old_container, new_container = old_containers[0], new_containers[0]
        require(old_container.get("Name") == new_container.get("Name"), "Reapuntar BD cambia nombre de contenedor")
        env_names = {"DATABASE_HOST", "KEYCLOAK_DB_URL", "KC_DB_URL"}
        def normalize(container, check_target):
            env = container.get("Environment", [])
            found = set()
            for item in env:
                if item.get("Name") in env_names:
                    found.add(item["Name"])
                    if check_target:
                        expected = host if item["Name"] == "DATABASE_HOST" else f"jdbc:postgresql://{host}:5432/sagrilaft"
                        require(item.get("Value") == expected, "Task definition no apunta al host de BD aprobado")
                    item["Value"] = "<database-endpoint>"
            return found
        old_fields = normalize(old_container, False)
        new_fields = normalize(new_container, True)
        require(old_fields == new_fields and new_fields, "No se identificaron campos de conexión de BD consistentes")
        require(old_props == new_props, f"Reapuntar BD altera imágenes u otra configuración: {logical_id}")
        changed_containers.add(new_container["Name"])
    require(changed_containers == {"backend", "keycloak", "migration"},
            "Reapuntar BD debe cambiar solo backend, Keycloak y task de migración")
    require(len(changed_services) == 4, "Reapuntar BD debe activar exactamente los cuatro servicios P20 desde cero")
    old_outputs, new_outputs = copy.deepcopy(original.get("Outputs", {})), copy.deepcopy(target.get("Outputs", {}))
    require("EcsDatabaseHost" in old_outputs and "EcsDatabaseHost" in new_outputs,
            "Template P20 sin output del host de BD")
    old_outputs.pop("EcsDatabaseHost")
    new_output = new_outputs.pop("EcsDatabaseHost")
    require("EcsDesiredCount" in old_outputs and "EcsDesiredCount" in new_outputs,
            "Template P20 sin output de capacidad ECS")
    old_outputs.pop("EcsDesiredCount")
    new_count_output = new_outputs.pop("EcsDesiredCount")
    require(new_output["Value"] == host and new_count_output["Value"] == str(desired_count)
            and old_outputs == new_outputs,
            "Reapuntar BD modifica outputs adicionales o no registra el host esperado")


def coordinate_p20_service_rollback(rt, execute=False):
    """Rollback solo de las cuatro aplicaciones P20; nunca ejecuta Alembic."""
    p = rt.plan
    require(bool(re.fullmatch(r"p20-[a-f0-9]{12}", p["environment"])), "Rollback solo permitido en stack P20")
    require(p.get("previous_tag") != p.get("candidate_tag"), "Tags previo/candidato deben diferir")
    require(rt.aws("sts", "get-caller-identity")["Account"] == p["account"], "Cuenta activa incorrecta")
    outputs = stack_state(rt)
    count = p["desired_count"]
    require(int(outputs["EcsDesiredCount"]) == count and count > 0,
            "Capacidad P20 no coincide con el plan de rollback")
    baseline = deployed_template(rt)
    rt.save("rollback-baseline.json", baseline)
    rt.save("rollback-current-services.json", services(rt, outputs, p["candidate_tag"], count))
    verify_tag_digests(rt, outputs, p["previous_tag"], p["previous_digests"])
    migration_tag = outputs["EcsMigrationImageTag"]
    rollback = rt.synth("rollback", p["previous_tag"], migration_tag, count)
    assert_service_rollback_transition(baseline, rollback, environment=p["environment"])
    rt.save("rollback-template.json", rollback)
    rt.event({"event": "p20_service_rollback_preflight_validated",
              "planHash": fingerprint(p), "templateHash": fingerprint(rollback),
              "migrationTagPreserved": migration_tag, "migrationWillRun": False})
    if not execute:
        return
    lock_file = rt.directory / "lock.json"
    run_id = uuid.uuid4().hex
    rt.save("lock.json", {"runId": run_id, "planHash": fingerprint(p)})
    bucket, key = outputs["S3Bucket"], f"_deployment/{rt.stack}.lock"
    rt.event({"event": "lock_requested", "bucket": bucket, "key": key, "runId": run_id,
              "operation": "p20-service-rollback"})
    lock = rt.aws("s3api", "put-object", "--bucket", bucket, "--key", key, "--body", str(lock_file),
                  "--if-none-match", "*", "--expected-bucket-owner", p["account"])
    etag = lock["ETag"]

    def assert_lock():
        current = rt.aws("s3api", "head-object", "--bucket", bucket, "--key", key,
                         "--expected-bucket-owner", p["account"])
        require(current["ETag"] == etag, "Se perdió el bloqueo del rollback P20")

    require(stack_state(rt) == outputs
            and comparison_template(deployed_template(rt), p["environment"], preserve_metadata=True)
            == comparison_template(baseline, p["environment"], preserve_metadata=True),
            "Stack cambió después del preflight de rollback")
    services(rt, outputs, p["candidate_tag"], count)
    verify_tag_digests(rt, outputs, p["previous_tag"], p["previous_digests"])
    assert_lock()
    rt.deploy("rollback")
    outputs = stack_state(rt)
    require(comparison_template(deployed_template(rt), p["environment"])
            == comparison_template(rollback, p["environment"]), "Rollback no coincide con template revisado")
    rt.save("rollback-final-services.json", services(rt, outputs, p["previous_tag"], count))
    rt.smoke()
    assert_lock()
    rt.aws("s3api", "delete-object", "--bucket", bucket, "--key", key,
           "--if-match", etag, "--expected-bucket-owner", p["account"])
    rt.event({"event": "p20_service_rollback_completed", "runId": run_id,
              "previousTag": p["previous_tag"], "migrationWillRun": False})


def assert_p20_baseline_activation_transition(before, after, desired_count, environment=None):
    """From zero, permit only four app task definitions and desired count."""
    original = comparison_template(before, environment)
    target = comparison_template(after, environment)
    old_outputs, new_outputs = original.get("Outputs", {}), target.get("Outputs", {})
    require(old_outputs.get("EcsDesiredCount", {}).get("Value") == "0"
            and new_outputs.get("EcsDesiredCount", {}).get("Value") == str(desired_count),
            "Activación baseline P20 debe cambiar capacidad de cero al valor planeado")
    new_outputs["EcsDesiredCount"] = copy.deepcopy(old_outputs["EcsDesiredCount"])
    old_services = {key: value for key, value in original["Resources"].items()
                    if value["Type"] == "AWS::ECS::Service"}
    new_services = {key: value for key, value in target["Resources"].items()
                    if value["Type"] == "AWS::ECS::Service"}
    require(len(old_services) == len(new_services) == 4, "Se requieren exactamente cuatro servicios ECS")
    for key in old_services:
        old_props, new_props = old_services[key]["Properties"], new_services[key]["Properties"]
        require(old_props.get("DesiredCount") == 0 and new_props.get("DesiredCount") == desired_count,
                f"Capacidad inicial ECS no coincide: {key}")
        new_props["DesiredCount"] = 0
    assert_service_rollback_transition(original, target)


def verify_p20_target_health(rt, services_response):
    summary = []
    for service in services_response:
        groups = service.get("loadBalancers", [])
        require(len(groups) == 1 and groups[0].get("targetGroupArn"),
                "Cada servicio P20 debe tener exactamente un target group")
        response = rt.aws("elbv2", "describe-target-health", "--target-group-arn",
                          groups[0]["targetGroupArn"])
        targets = response.get("TargetHealthDescriptions", [])
        require(len(targets) >= service["desiredCount"]
                and all(item.get("TargetHealth", {}).get("State") == "healthy" for item in targets),
                "La release anterior no está saludable en los target groups")
        summary.append({"service": service["serviceName"], "healthyTargets": len(targets)})
    return summary


def require_p20_services_stopped(rt, outputs):
    response = rt.aws("ecs", "describe-services", "--cluster", outputs["EcsClusterName"],
                      "--services", *(outputs[key] for key in SERVICES.values()))
    require(not response.get("failures") and len(response.get("services", [])) == 4,
            "No se pueden verificar los cuatro servicios P20 en cero")
    for service in response["services"]:
        require(service.get("status") == "ACTIVE" and service.get("desiredCount") == 0
                and service.get("runningCount") == 0 and service.get("pendingCount") == 0,
                "Activación baseline requiere servicios ECS P20 detenidos")
        deployments = service.get("deployments", [])
        require(len(deployments) == 1 and deployments[0].get("rolloutState") == "COMPLETED",
                "Servicio P20 tiene despliegue en curso o fallido")
    return response["services"]


def coordinate_p20_activate_previous(rt, execute=False):
    """Initialize a healthy P20 baseline without invoking Alembic."""
    p = rt.plan
    require(bool(re.fullmatch(r"p20-[a-f0-9]{12}", p["environment"])),
            "Activar baseline solo está permitido en P20")
    require(p["desired_count"] == 1, "Baseline P20 debe comenzar con una tarea por servicio")
    require(rt.aws("sts", "get-caller-identity")["Account"] == p["account"], "Cuenta activa incorrecta")
    outputs = stack_state(rt)
    require(outputs["EcsDesiredCount"] == "0", "Baseline solo activa servicios que están en cero")
    require_p20_services_stopped(rt, outputs)
    verify_tag_digests(rt, outputs, p["previous_tag"], p["previous_digests"])
    baseline = deployed_template(rt)
    rt.save("p20-baseline-template.json", baseline)
    active = rt.synth("activate-previous", p["previous_tag"], outputs["EcsMigrationImageTag"], 1)
    assert_p20_baseline_activation_transition(baseline, active, 1, environment=p["environment"])
    rt.event({"event": "p20_previous_activation_preflight_validated",
              "planHash": fingerprint(p), "templateHash": fingerprint(active),
              "previousTag": p["previous_tag"], "migrationWillRun": False})
    if not execute:
        return

    lock_file = rt.directory / "lock.json"
    run_id = uuid.uuid4().hex
    rt.save("lock.json", {"runId": run_id, "planHash": fingerprint(p)})
    bucket, key = outputs["S3Bucket"], f"_deployment/{rt.stack}.lock"
    rt.event({"event": "lock_requested", "bucket": bucket, "key": key, "runId": run_id,
              "operation": "p20-activate-previous"})
    lock = rt.aws("s3api", "put-object", "--bucket", bucket, "--key", key,
                  "--body", str(lock_file), "--if-none-match", "*", "--expected-bucket-owner", p["account"])
    etag = lock["ETag"]

    def assert_lock():
        current = rt.aws("s3api", "head-object", "--bucket", bucket, "--key", key,
                         "--expected-bucket-owner", p["account"])
        require(current["ETag"] == etag, "Se perdió el lock de activación baseline P20")

    require(stack_state(rt) == outputs
            and comparison_template(deployed_template(rt), p["environment"], preserve_metadata=True)
            == comparison_template(baseline, p["environment"], preserve_metadata=True),
            "Stack P20 cambió después del preflight baseline")
    require_p20_services_stopped(rt, outputs)
    assert_lock()
    rt.deploy("activate-previous")
    outputs = stack_state(rt)
    require(comparison_template(deployed_template(rt), p["environment"])
            == comparison_template(active, p["environment"]), "Activación baseline no coincide con plantilla")
    final = services(rt, outputs, p["previous_tag"], 1)
    for service in final:
        kind = next(name for name, output_key in SERVICES.items() if outputs[output_key] == service["serviceName"])
        require(service["verifiedTasks"] and all(task["imageDigest"] == p["previous_digests"][kind]
                for task in service["verifiedTasks"]), f"Digest baseline no coincide para {kind}")
    target_health = verify_p20_target_health(rt, final)
    rt.save("p20-baseline-services.json", final)
    rt.save("p20-baseline-target-health.json", target_health)
    assert_lock()
    rt.aws("s3api", "delete-object", "--bucket", bucket, "--key", key,
           "--if-match", etag, "--expected-bucket-owner", p["account"])
    rt.event({"event": "p20_previous_activation_completed", "runId": run_id,
              "previousTag": p["previous_tag"], "targetHealthVerified": True,
              "migrationWillRun": False})


def verify_restored_database(rt, outputs):
    context = rt.plan["context"]
    identifier, expected_host = context["restoredDbIdentifier"], context["databaseHostOverride"]
    response = rt.aws("rds", "describe-db-instances", "--db-instance-identifier", identifier)
    instances = response.get("DBInstances", [])
    require(len(instances) == 1, "No se encontró una única instancia RDS restaurada")
    instance = instances[0]
    require(instance.get("DBInstanceStatus") == "available", "La BD restaurada no está available")
    require(instance.get("Endpoint", {}).get("Address") == expected_host, "Host RDS no coincide con el plan")
    require(instance.get("DBSubnetGroup", {}).get("VpcId") == outputs.get("P20VpcId"),
            "La BD restaurada no pertenece a la VPC del laboratorio")
    attached = {group.get("VpcSecurityGroupId") for group in instance.get("VpcSecurityGroups", [])}
    require(outputs.get("P20RdsSecurityGroupId") in attached,
            "La BD restaurada no usa el Security Group RDS aislado de P20")
    tags = rt.aws("rds", "list-tags-for-resource", "--resource-name", instance["DBInstanceArn"]).get("TagList", [])
    tag_map = {tag.get("Key"): tag.get("Value") for tag in tags}
    require(tag_map.get("Project") == "sagrilaft" and tag_map.get("Environment") == rt.plan["environment"],
            "La BD restaurada no tiene etiquetas de propiedad P20")
    return {"identifier": identifier, "host": expected_host, "status": instance["DBInstanceStatus"],
            "vpcId": outputs["P20VpcId"], "securityGroupId": outputs["P20RdsSecurityGroupId"]}


def coordinate_p20_database_repoint(rt, execute=False):
    """Cambia las referencias de BD en task definitions P20 sin ejecutar Alembic."""
    p = rt.plan
    require(bool(re.fullmatch(r"p20-[a-f0-9]{12}", p["environment"])), "Reapuntar BD solo permitido en P20")
    require(rt.aws("sts", "get-caller-identity")["Account"] == p["account"], "Cuenta activa incorrecta")
    outputs = stack_state(rt)
    count = p["desired_count"]
    require(count > 0 and int(outputs["EcsDesiredCount"]) == 0,
            "La conexión debe partir con los cuatro servicios detenidos y una capacidad final explícita")
    db_evidence = verify_restored_database(rt, outputs)
    baseline = deployed_template(rt)
    rt.save("repoint-baseline.json", baseline)
    rt.save("repoint-current-services.json", services(rt, outputs, p["candidate_tag"], 0))
    verify_images(rt, outputs)
    migration_tag = outputs["EcsMigrationImageTag"]
    target = rt.synth("repoint-restored-db", p["candidate_tag"], migration_tag, count)
    assert_database_repoint_transition(baseline, target, p["context"]["databaseHostOverride"], count)
    rt.save("repoint-template.json", target)
    rt.save("restored-db-evidence.json", db_evidence)
    rt.event({"event": "p20_restored_database_repoint_preflight_validated",
              "planHash": fingerprint(p), "templateHash": fingerprint(target), "migrationWillRun": False})
    if not execute:
        return

    lock_file = rt.directory / "lock.json"
    run_id = uuid.uuid4().hex
    rt.save("lock.json", {"runId": run_id, "planHash": fingerprint(p)})
    bucket, key = outputs["S3Bucket"], f"_deployment/{rt.stack}.lock"
    rt.event({"event": "lock_requested", "bucket": bucket, "key": key, "runId": run_id,
              "operation": "p20-restored-db-repoint"})
    lock = rt.aws("s3api", "put-object", "--bucket", bucket, "--key", key, "--body", str(lock_file),
                  "--if-none-match", "*", "--expected-bucket-owner", p["account"])
    etag = lock["ETag"]

    def assert_lock():
        current = rt.aws("s3api", "head-object", "--bucket", bucket, "--key", key,
                         "--expected-bucket-owner", p["account"])
        require(current["ETag"] == etag, "Se perdió el bloqueo de conexión a RDS restaurada")

    require(stack_state(rt) == outputs
            and comparison_template(deployed_template(rt), p["environment"], preserve_metadata=True)
            == comparison_template(baseline, p["environment"], preserve_metadata=True),
            "Stack cambió después del preflight de conexión a RDS")
    verify_restored_database(rt, outputs)
    services(rt, outputs, p["candidate_tag"], count)
    assert_lock()
    rt.deploy("repoint-restored-db")
    outputs = stack_state(rt)
    require(comparison_template(deployed_template(rt), p["environment"])
            == comparison_template(target, p["environment"]), "Conexión a BD restaurada no coincide con template revisado")
    rt.save("repoint-final-services.json", services(rt, outputs, p["candidate_tag"], count))
    rt.smoke()
    assert_lock()
    rt.aws("s3api", "delete-object", "--bucket", bucket, "--key", key,
           "--if-match", etag, "--expected-bucket-owner", p["account"])
    rt.event({"event": "p20_restored_database_repoint_completed", "runId": run_id,
              "databaseIdentifier": db_evidence["identifier"], "migrationWillRun": False})


def migration_environment(rt, outputs):
    definition = rt.aws("ecs", "describe-task-definition", "--task-definition", outputs["EcsMigrationTaskDefinitionArn"])["taskDefinition"]
    container = definition["containerDefinitions"][0]
    env = {x["name"]: x["value"] for x in container["environment"]}
    database_host = rt.plan["context"].get("databaseHostOverride") or outputs["RdsEndpoint"]
    require(env["DATABASE_HOST"] == database_host and env["DATABASE_NAME"] == outputs["KeycloakDbName"], "BD de migración no corresponde al stack")
    secrets = {x["name"]: x["valueFrom"] for x in container["secrets"]}
    for key, field in (("DB_USER", "username"), ("DB_PASSWORD", "password")):
        require(secrets[key] == outputs["DbSecretArn"] + f":{field}::", "Credenciales BD no corresponden al stack")
    name = outputs["RuntimeConfigPrefix"] + "APP_ENV"
    require(secrets["APP_ENV"] == f"arn:aws:ssm:{rt.plan['region']}:{rt.plan['account']}:parameter{name}", "Referencia APP_ENV incorrecta")
    parameter = rt.aws("ssm", "get-parameter", "--name", name)["Parameter"]["Value"]
    require(parameter == ("production" if rt.plan["environment"] == "prod" else "staging"), "APP_ENV no corresponde al ambiente")
    return container


def schema_evidence(rt, completion, sleep=time.sleep, clock=time.monotonic):
    require(completion.get("logGroup") and completion.get("logStream"), "Falta referencia de logs de la tarea")
    deadline = clock() + 60
    while clock() < deadline:
        events, token = [], None
        # Paginación acotada; exceso se considera evidencia incompleta.
        for _ in range(100):
            args = ["--log-group-name", completion["logGroup"], "--log-stream-name", completion["logStream"], "--start-from-head"]
            if token:
                args += ["--next-token", token]
            page = rt.aws("logs", "get-log-events", *args)
            for item in page.get("events", []):
                try:
                    event = json.loads(item["message"])
                except (ValueError, TypeError):
                    continue
                if isinstance(event, dict) and event.get("event") in ("migration_before", "migration_schema_verified"):
                    events.append(event)
            following = page.get("nextForwardToken")
            if not following or following == token:
                break
            token = following
        else:
            raise MigrationError("Demasiadas páginas de logs; evidencia incompleta")
        before = [x for x in events if x["event"] == "migration_before"]
        after = [x for x in events if x["event"] == "migration_schema_verified"]
        if before and after:
            require(len(before) == len(after) == 1 and events.index(before[0]) < events.index(after[0]), "Evidencia de esquema ambigua")
            require(before[0]["revisions"] == rt.plan["previous_revisions"] and before[0]["expectedHead"] == rt.plan["expected_head"], "Revisión inicial no coincide con el plan")
            require(after[0]["revisions"] == [rt.plan["expected_head"]] and after[0]["expectedHead"] == rt.plan["expected_head"], "Revisión final no coincide con el plan")
            return {"taskArn": completion["taskArn"], "imageDigest": completion["imageDigest"], "schemaVerified": True,
                    "before": before[0], "after": after[0]}
        sleep(2)
    raise MigrationError("No hay evidencia suficiente del esquema; no activar")


def coordinate(rt, execute=False):
    p = rt.plan
    validate_plan(p)
    if p.get("p20_operation") == "activate-previous":
        return coordinate_p20_activate_previous(rt, execute)
    if p.get("p20_operation") == "rollback-services":
        return coordinate_p20_service_rollback(rt, execute)
    if p.get("p20_operation") == "connect-restored-db":
        return coordinate_p20_database_repoint(rt, execute)
    require(rt.aws("sts", "get-caller-identity")["Account"] == p["account"], "Cuenta activa incorrecta")
    outputs = stack_state(rt)
    bootstrap = p["mode"] == "bootstrap"
    count = 0 if bootstrap else p["desired_count"]
    require(int(outputs["EcsDesiredCount"]) == count, "Capacidad declarada no coincide")
    baseline = deployed_template(rt)
    rt.save("baseline.json", baseline)
    rt.save("previous-services.json", services(rt, outputs, p["previous_tag"], count))
    verify_images(rt, outputs)
    prepare = rt.synth("prepare", p["previous_tag"], p["candidate_tag"], count)
    activate = rt.synth("activate", p["candidate_tag"], p["candidate_tag"], p["desired_count"])
    assert_transition(baseline, prepare, "prepare", environment=p["environment"])
    assert_transition(prepare, activate, "activate", bootstrap, environment=p["environment"])
    rt.event({"event": "plan_validated", "planHash": fingerprint(p), "prepareHash": fingerprint(prepare), "activateHash": fingerprint(activate)})
    if not execute:
        return
    lock_file = rt.directory / "lock.json"
    run_id = uuid.uuid4().hex
    rt.save("lock.json", {"runId": run_id, "planHash": fingerprint(p)})
    bucket, key = outputs["S3Bucket"], f"_deployment/{rt.stack}.lock"
    rt.event({"event": "lock_requested", "bucket": bucket, "key": key, "runId": run_id})
    lock = rt.aws("s3api", "put-object", "--bucket", bucket, "--key", key, "--body", str(lock_file),
                  "--if-none-match", "*", "--expected-bucket-owner", p["account"])
    etag = lock["ETag"]
    # No finally-delete: ante fallo/timeout/interrupción conservar el bloqueo.
    def assert_lock():
        current = rt.aws("s3api", "head-object", "--bucket", bucket, "--key", key, "--expected-bucket-owner", p["account"])
        require(current["ETag"] == etag, "Se perdió el bloqueo del despliegue")
    require(stack_state(rt) == outputs and comparison_template(deployed_template(rt), p["environment"], preserve_metadata=True) == comparison_template(baseline, p["environment"], preserve_metadata=True), "Stack cambió después del preflight")
    services(rt, outputs, p["previous_tag"], count)
    assert_lock()
    rt.deploy("prepare")
    outputs = stack_state(rt)
    require(comparison_template(deployed_template(rt), p["environment"]) == comparison_template(prepare, p["environment"]), "Preparación no coincide con template inspeccionado")
    services(rt, outputs, p["previous_tag"], count)
    migration_environment(rt, outputs)
    service = rt.aws("ecs", "describe-services", "--cluster", outputs["EcsClusterName"],
                     "--services", outputs["EcsBackendServiceName"])["services"][0]
    network = service["networkConfiguration"]["awsvpcConfiguration"]
    require(network["securityGroups"] == [outputs["EcsSecurityGroupId"]], "Red del backend no coincide")
    values = {"AWS_REGION": p["region"], "AWS_ACCOUNT_ID": p["account"], "ECS_CLUSTER_NAME": outputs["EcsClusterName"],
              "ECS_MIGRATION_TASK_DEFINITION_ARN": outputs["EcsMigrationTaskDefinitionArn"],
              "ECS_SECURITY_GROUP_ID": outputs["EcsSecurityGroupId"], "ECS_PRIVATE_SUBNET_IDS": ",".join(network["subnets"]),
              "ECS_MIGRATION_EXPECTED_IMAGE": outputs["EcrBackendUri"] + ":" + p["candidate_tag"],
              "ECS_MIGRATION_EXPECTED_DIGEST": p["digests"]["backend"], "ECS_MIGRATION_CLIENT_TOKEN": run_id}
    if p.get("p20_migration_fault"):
        values["ECS_MIGRATION_ENVIRONMENT"] = p["environment"]
        values["ECS_MIGRATION_P20_FAULT"] = p["p20_migration_fault"]
    events = []
    def emit(line):
        event = json.loads(line)
        events.append(event)
        rt.event(event)
    assert_lock()
    with environment(values):
        run_migration(rt.aws, emit=emit)
    completed = [x for x in events if x.get("event") == "migration_completed"]
    require(len(completed) == 1, "Falta resultado inequívoco de la migración")
    proof = schema_evidence(rt, completed[0])
    rt.save("schema-evidence.json", proof)
    rt.event({"event": "schema_verified", **proof})
    assert_lock()
    require(comparison_template(deployed_template(rt), p["environment"]) == comparison_template(prepare, p["environment"]), "Stack cambió durante la migración")
    stack_state(rt)
    services(rt, outputs, p["previous_tag"], count)
    verify_images(rt, outputs)
    rt.deploy("activate")
    outputs = stack_state(rt)
    require(comparison_template(deployed_template(rt), p["environment"]) == comparison_template(activate, p["environment"]), "Activación no coincide con template aprobado")
    rt.save("active-services.json", services(rt, outputs, p["candidate_tag"], p["desired_count"]))
    if p.get("smoke_mode") == "manual":
        assert_lock()
        pending = {"status": "pending_manual", "runId": run_id, "planHash": fingerprint(p),
                   "candidate": p["candidate_tag"], "environment": p["environment"],
                   "startedAt": utc_now(), "bucket": bucket, "key": key, "etag": etag,
                   "activateHash": fingerprint(comparison_template(activate, p["environment"])), "schemaHash": fingerprint(proof)}
        rt.save("manual-state.json", pending)
        rt.save("manual-validation.json", {
            "runId": run_id, "planHash": fingerprint(p), "environment": p["environment"],
            "candidate": p["candidate_tag"], "status": "pending", "operator": "", "completedAt": "",
            "formularioId": "", "accesoId": "", "retention": "retained_no_delete_endpoint",
            "checks": {name: {"status": "pending", "evidence": []} for name in MANUAL_CHECKS}})
        rt.event({"event": "manual_validation_pending", "runId": run_id, "candidate": p["candidate_tag"]})
        return 3
    rt.smoke()
    assert_lock()
    rt.aws("s3api", "delete-object", "--bucket", bucket, "--key", key, "--if-match", etag,
           "--expected-bucket-owner", p["account"])
    rt.event({"event": "release_completed", "candidate": p["candidate_tag"]})


def read_json(path):
    return json.loads(path.read_text())


def review_manual(rt):
    """Comprueba evidencia humana local. No interpreta capturas ni sustituye al revisor."""
    p = rt.plan
    validate_plan(p)
    require(p.get("smoke_mode") == "manual", "El plan no admite cierre manual")
    state = read_json(rt.directory / "manual-state.json")
    record = read_json(rt.directory / "manual-validation.json")
    require(state["status"] == "pending_manual", "La ejecución no está pendiente de validación manual")
    for source in (state, record):
        require(source["planHash"] == fingerprint(p) and source["candidate"] == p["candidate_tag"]
                and source["environment"] == p["environment"], "Evidencia de otro plan, SHA o ambiente")
    lock = read_json(rt.directory / "lock.json")
    require(state["runId"] == record["runId"] == lock["runId"]
            and lock["planHash"] == state["planHash"], "Evidencia de otra ejecución")
    require(record["status"] == "approved", "Validación manual pendiente o fallida; conservar bloqueo")
    require(all(isinstance(record.get(k), str) and record[k].strip()
                for k in ("operator", "formularioId", "accesoId")), "Faltan responsable o IDs de prueba")
    require(record.get("retention") == "retained_no_delete_endpoint", "Falta constancia de conservación")
    started = datetime.fromisoformat(state["startedAt"])
    completed = datetime.fromisoformat(record["completedAt"])
    require(started.tzinfo is not None and completed.tzinfo is not None, "Fechas requieren zona horaria")
    require(started <= completed <= datetime.now(timezone.utc), "Fecha de validación fuera de la ejecución")
    require(set(record["checks"]) == set(MANUAL_CHECKS), "Comprobaciones incompletas")
    artifacts = {}
    for check in record["checks"].values():
        require(check["status"] == "passed" and isinstance(check["evidence"], list)
                and check["evidence"], "Comprobación sin aprobar o sin evidencia")
        for name in check["evidence"]:
            require(isinstance(name, str) and bool(name), "Referencia de evidencia inválida")
            path = (rt.directory / name).resolve()
            require(not Path(name).is_absolute() and path.is_relative_to(rt.directory.resolve()),
                    "Evidencia debe estar dentro del directorio de ejecución")
            require(path.is_file() and path.stat().st_size > 0, "Archivo de evidencia ausente o vacío")
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    schema = read_json(rt.directory / "schema-evidence.json")
    require(fingerprint(schema) == state["schemaHash"] and schema["schemaVerified"] is True
            and schema["after"]["revisions"] == [p["expected_head"]], "Evidencia Alembic no corresponde")
    require(state["key"] == f"_deployment/{rt.stack}.lock", "Clave de bloqueo incorrecta")
    return state, record, artifacts


def close_manual(rt, execute=False):
    """Sin execute revisa solo archivos. Con execute consulta AWS y libera solo el lock propio."""
    state, record, artifacts = review_manual(rt)
    if not execute:
        rt.event({"event": "manual_evidence_reviewed_locally", "runId": state["runId"]})
        return 0
    p = rt.plan
    require(rt.aws("sts", "get-caller-identity")["Account"] == p["account"], "Cuenta activa incorrecta")
    outputs = stack_state(rt)
    require(outputs["S3Bucket"] == state["bucket"], "Bucket del bloqueo no corresponde")
    def check_lock():
        current = rt.aws("s3api", "head-object", "--bucket", state["bucket"], "--key", state["key"],
                         "--expected-bucket-owner", p["account"])
        require(current["ETag"] == state["etag"], "Se perdió el bloqueo del despliegue")
    check_lock()
    require(fingerprint(comparison_template(deployed_template(rt), p["environment"])) == state["activateHash"],
            "Stack cambió desde la activación; reconciliar")
    rt.save("manual-close-services.json", services(rt, outputs, p["candidate_tag"], p["desired_count"]))
    # Volver a leer antes de liberar: no admitir evidencia cambiada durante las consultas.
    require(review_manual(rt) == (state, record, artifacts), "Evidencia cambió durante el cierre")
    check_lock()
    rt.save("manual-accepted.json", {"record": record, "artifactSha256": artifacts, "acceptedAt": utc_now()})
    rt.event({"event": "manual_validation_accepted", "runId": state["runId"]})
    rt.aws("s3api", "delete-object", "--bucket", state["bucket"], "--key", state["key"],
           "--if-match", state["etag"], "--expected-bucket-owner", p["account"])
    rt.save("manual-state.json", {**state, "status": "completed", "completedAt": utc_now()})
    rt.event({"event": "release_completed", "candidate": p["candidate_tag"], "runId": state["runId"]})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--environment", required=True,
                        help="staging, prod o p20-<runId de 12 caracteres hexadecimales>")
    parser.add_argument("--evidence-dir", type=Path, required=True, help="Directorio privado; nuevo salvo para cierre manual")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--close-manual", action="store_true",
                        help="Revisar evidencia local; con --execute verifica AWS y libera lock, sin deploy/migración")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        plan = read_json(args.plan)
        validate_plan(plan)
        require(plan["environment"] == args.environment, "Ambiente del plan distinto al solicitado")
        directory = args.evidence_dir.resolve()
        if args.close_manual:
            require(directory.is_dir(), "Falta directorio de ejecución")
            require(read_json(directory / "plan.json") == plan, "Plan distinto al de la ejecución")
            # Serializa cierres desde la misma evidencia local; S3 protege contra otro propietario.
            with (directory / ".manual-close.lock").open("a") as mutex:
                fcntl.flock(mutex, fcntl.LOCK_EX | fcntl.LOCK_NB)
                rt = Runtime(plan, directory)
                record_orchestrator(rt, "orchestrator-close-" + uuid.uuid4().hex)
                return close_manual(rt, args.execute)
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        rt = Runtime(plan, directory)
        rt.save("plan.json", plan)
        record_orchestrator(rt)
        return coordinate(rt, args.execute) or 0
    except MigrationError as error:
        print(f"ERROR: {error}. Revisar evidencia y reconciliar el bloqueo; no hay rollback automático.", flush=True)
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
        print("ERROR: flujo detenido. Revisar evidencia privada; si se solicitó el bloqueo, reconciliar antes de retirarlo. No hay rollback automático.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
