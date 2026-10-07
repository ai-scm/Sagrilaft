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
    require(p["environment"] in ("staging", "prod"), "Ambiente inválido")
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
    reserved = {"environment", "account", "region", "imageTag", "migrationImageTag", "desiredCount"}
    require(not reserved.intersection(p["context"]), "Contexto no puede sobrescribir ambiente/tags/capacidad")
    required_context = {"hostedZoneName", "hostedZoneId", "domainName", "portalDomainName",
                        "keycloakDomainName", "certificateArn", "bedrockModelId", "zohoSecretYaExiste",
                        "proveedorListasCautela", "habilitarNatEgress", "snsAlertasSub"}
    require(required_context.issubset(p["context"]), "Falta contexto CDK explícito del ambiente")
    require(all(isinstance(v, (str, bool, int)) for v in p["context"].values()), "Contexto debe contener valores escalares")


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


def comparison_template(value, environment=None, *, preserve_metadata=False):
    """Equivalencias exactas, conservando el criterio de metadata de cada comprobación."""
    result = copy.deepcopy(value if preserve_metadata else strip_metadata(value))
    if environment != "staging":
        return result
    for path, original, observed in STAGING_UNICODE_PAIRS:
        cursor = result
        try:
            for key in path[:-1]:
                cursor = cursor[key]
            if cursor[path[-1]] == observed:
                cursor[path[-1]] = original
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


def migration_environment(rt, outputs):
    definition = rt.aws("ecs", "describe-task-definition", "--task-definition", outputs["EcsMigrationTaskDefinitionArn"])["taskDefinition"]
    container = definition["containerDefinitions"][0]
    env = {x["name"]: x["value"] for x in container["environment"]}
    require(env["DATABASE_HOST"] == outputs["RdsEndpoint"] and env["DATABASE_NAME"] == outputs["KeycloakDbName"], "BD de migración no corresponde al stack")
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
    parser.add_argument("--environment", choices=("staging", "prod"), required=True)
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
