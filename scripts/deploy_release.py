#!/usr/bin/env python3
"""Preparar -> migrar -> verificar evidencia -> activar -> smoke.

Sin --execute solo consulta AWS y sintetiza localmente, sin mutaciones AWS.
Requiere stack existente: modo compatible, o bootstrap ya creado con cero tareas.
No construye imágenes, no crea el bootstrap ni hace rollback automático.

Plan JSON (sin secretos): environment, account, region, mode (compatible/bootstrap),
previous_tag, candidate_tag (SHA Git completo), desired_count, expected_head,
previous_revisions (lista), digests (backend/formulario-publico/portal-interno/keycloak),
context (contexto CDK completo), smoke_command (lista de argumentos ejecutables).
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
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
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


def assert_transition(before, after, phase, bootstrap=False):
    """Rechaza cambios fuera de imagen/SHA; bootstrap admite capacidad/autoscaling."""
    before = strip_metadata(before)
    normalized = copy.deepcopy(strip_metadata(after))
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
        (self.directory / name).write_text(json.dumps(value, indent=2) + "\n")

    def event(self, value):
        with (self.directory / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
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
    assert_transition(baseline, prepare, "prepare")
    assert_transition(prepare, activate, "activate", bootstrap)
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
    require(stack_state(rt) == outputs and deployed_template(rt) == baseline, "Stack cambió después del preflight")
    services(rt, outputs, p["previous_tag"], count)
    assert_lock()
    rt.deploy("prepare")
    outputs = stack_state(rt)
    require(strip_metadata(deployed_template(rt)) == strip_metadata(prepare), "Preparación no coincide con template inspeccionado")
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
    require(strip_metadata(deployed_template(rt)) == strip_metadata(prepare), "Stack cambió durante la migración")
    stack_state(rt)
    services(rt, outputs, p["previous_tag"], count)
    verify_images(rt, outputs)
    rt.deploy("activate")
    outputs = stack_state(rt)
    require(strip_metadata(deployed_template(rt)) == strip_metadata(activate), "Activación no coincide con template aprobado")
    rt.save("active-services.json", services(rt, outputs, p["candidate_tag"], p["desired_count"]))
    rt.smoke()
    assert_lock()
    rt.aws("s3api", "delete-object", "--bucket", bucket, "--key", key, "--if-match", etag,
           "--expected-bucket-owner", p["account"])
    rt.event({"event": "release_completed", "candidate": p["candidate_tag"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--environment", choices=("staging", "prod"), required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True, help="Directorio nuevo, privado, fuera de Git")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        plan = json.loads(args.plan.read_text())
        validate_plan(plan)
        require(plan["environment"] == args.environment, "Ambiente del plan distinto al solicitado")
        directory = args.evidence_dir.resolve()
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        rt = Runtime(plan, directory)
        rt.save("plan.json", plan)
        coordinate(rt, args.execute)
        return 0
    except MigrationError as error:
        print(f"ERROR: {error}. Revisar evidencia y reconciliar el bloqueo; no hay rollback automático.", flush=True)
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
        print("ERROR: flujo detenido. Revisar evidencia privada; si se solicitó el bloqueo, reconciliar antes de retirarlo. No hay rollback automático.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
