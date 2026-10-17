#!/usr/bin/env python3
"""Lanza una migración ECS y verifica su resultado, sin activar servicios.

Variables requeridas:
  AWS_ACCOUNT_ID, ECS_CLUSTER_NAME, ECS_MIGRATION_TASK_DEFINITION_ARN,
  ECS_SECURITY_GROUP_ID, ECS_PRIVATE_SUBNET_IDS,
  ECS_MIGRATION_EXPECTED_IMAGE (URI ECR con tag),
  ECS_MIGRATION_EXPECTED_DIGEST (sha256:...), ECS_MIGRATION_CLIENT_TOKEN.
Reutilizar el mismo token y parámetros al reconciliar un intento incierto.
AWS_REGION: us-east-1; ECS_MIGRATION_TIMEOUT_SECONDS: 900.

El éxito acredita imagen/exitCode, NO la revisión final del esquema. Esa
comprobación pertenece al contenedor y se añadirá en otra fase. Un tag mutable
puede cambiar entre la comprobación ECR y el pull: no sustituye pinning/inmutabilidad.
"""

import json
import os
import re
import subprocess
import sys
import time


class MigrationError(Exception):
    pass


def require(name):
    value = os.environ.get(name, "")
    if not value:
        raise MigrationError(f"Falta {name}")
    return value


def check(condition, message):
    if not condition:
        raise MigrationError(message)


def run_migration(aws, emit=print, sleep=time.sleep, clock=time.monotonic):
    """AWS recibe servicio, operación y argumentos CLI; devuelve JSON parseado."""
    account = require("AWS_ACCOUNT_ID")
    region = os.environ.get("AWS_REGION", "us-east-1")
    cluster = require("ECS_CLUSTER_NAME")
    definition = require("ECS_MIGRATION_TASK_DEFINITION_ARN")
    group = require("ECS_SECURITY_GROUP_ID")
    subnets = require("ECS_PRIVATE_SUBNET_IDS").split(",")
    image = require("ECS_MIGRATION_EXPECTED_IMAGE")
    digest = require("ECS_MIGRATION_EXPECTED_DIGEST")
    token = require("ECS_MIGRATION_CLIENT_TOKEN")
    check(bool(re.fullmatch(r"\d{12}", account)), "AWS_ACCOUNT_ID invalido")
    check(bool(re.fullmatch(r"[a-z0-9-]+", region)), "AWS_REGION invalida")
    check(bool(re.fullmatch(r"[A-Za-z0-9_-]{1,255}", cluster)), "Use ECS_CLUSTER_NAME, no ARN")
    prefix = f"arn:aws:ecs:{region}:{account}:"
    check(bool(re.fullmatch(re.escape(prefix) + r"task-definition/[\w-]+:\d+", definition)),
          "Task definition debe ser un ARN con revision, cuenta y region esperadas")
    check(bool(re.fullmatch(r"sg-[0-9a-f]+", group)), "Security group invalido")
    check(all(re.fullmatch(r"subnet-[0-9a-f]+", subnet) for subnet in subnets), "Subnets invalidas")
    image_match = re.fullmatch(
        re.escape(f"{account}.dkr.ecr.{region}.amazonaws.com/")
        + r"([a-z0-9_./-]+):([A-Za-z0-9_][A-Za-z0-9_.-]{0,127})", image)
    check(image_match is not None, "Imagen ECR debe pertenecer a cuenta/region esperadas y tener tag")
    repository, tag = image_match.groups()
    check(tag not in ("latest", "bootstrap-placeholder", "synth-placeholder"), "Tag no ejecutable para migracion")
    check(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", digest)), "Digest esperado invalido")
    check(bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token)), "Client token invalido")
    try:
        timeout = int(os.environ.get("ECS_MIGRATION_TIMEOUT_SECONDS", "900"))
    except ValueError:
        raise MigrationError("Timeout debe ser entero") from None
    check(1 <= timeout <= 86400, "Timeout fuera de rango 1..86400")

    identity = aws("sts", "get-caller-identity")
    check(identity.get("Account") == account, "Cuenta AWS activa distinta de la esperada")
    clusters = aws("ecs", "describe-clusters", "--clusters", cluster)
    check(not clusters.get("failures") and len(clusters.get("clusters", [])) == 1, "Cluster no verificable")
    cluster_arn = prefix + "cluster/" + cluster
    check(clusters["clusters"][0].get("clusterArn") == cluster_arn
          and clusters["clusters"][0].get("status") == "ACTIVE", "Cluster incorrecto o inactivo")
    taskdef = aws("ecs", "describe-task-definition", "--task-definition", definition).get("taskDefinition", {})
    check(taskdef.get("taskDefinitionArn") == definition and taskdef.get("status") == "ACTIVE", "Task definition incorrecta o inactiva")
    containers = taskdef.get("containerDefinitions", [])
    check(len(containers) == 1 and containers[0].get("name") == "migration", "Se requiere un unico contenedor migration")
    container = containers[0]
    check(container.get("image") == image, "Imagen de task definition distinta de la esperada")
    env = {item["name"]: item.get("value") for item in container.get("environment", [])}
    check(env.get("RUN_MODE") == "migrate" and env.get("GIT_SHA") == tag, "RUN_MODE/GIT_SHA no corresponden a la migracion")
    check(taskdef.get("networkMode") == "awsvpc" and "FARGATE" in taskdef.get("requiresCompatibilities", []), "Task definition no compatible con Fargate/awsvpc")
    details = aws("ecr", "describe-images", "--repository-name", repository,
                  "--image-ids", f"imageTag={tag}").get("imageDetails", [])
    check(len(details) == 1 and details[0].get("imageDigest") == digest, "Digest ECR distinto del aprobado")
    log_options = container.get("logConfiguration", {}).get("options", {})
    # Seleccionar campos concretos; nunca imprimir environment, secrets o respuestas AWS completas.
    emit(json.dumps({"event": "migration_request", "clusterArn": cluster_arn,
                     "taskDefinitionArn": definition, "image": image, "expectedDigest": digest,
                     "clientToken": token, "logGroup": log_options.get("awslogs-group"),
                     "logRegion": log_options.get("awslogs-region")}))
    response = aws("ecs", "run-task", "--cluster", cluster_arn,
                   "--launch-type", "FARGATE", "--count", "1", "--task-definition", definition,
                   "--client-token", token, "--network-configuration",
                   json.dumps({"awsvpcConfiguration": {"subnets": subnets, "securityGroups": [group],
                                                       "assignPublicIp": "DISABLED"}}))
    tasks = response.get("tasks", [])
    # Conservar ARNs incluso si AWS devuelve simultáneamente failures.
    for task in tasks:
        arn = task.get("taskArn")
        if isinstance(arn, str) and arn.startswith(prefix + "task/"):
            emit(json.dumps({"event": "migration_launched", "taskArn": arn}))
    check(not response.get("failures") and len(tasks) == 1, "Lanzamiento fallido o incierto: reconciliar el intento; no activar")
    arn = tasks[0].get("taskArn", "")
    check(isinstance(arn, str) and arn.startswith(prefix + "task/"), "Task ARN ausente o inesperado")
    deadline = clock() + timeout
    while clock() < deadline:
        result = aws("ecs", "describe-tasks", "--cluster", cluster_arn, "--tasks", arn)
        failures = result.get("failures", [])
        current = result.get("tasks", [])
        # ECS puede no hacer visible la tarea inmediatamente tras run-task.
        if not current and (not failures or all(f.get("reason") == "MISSING" for f in failures)):
            sleep(min(5, max(0, deadline - clock())))
            continue
        check(not failures and len(current) == 1, "No se puede verificar la tarea; resultado incierto")
        task = current[0]
        check(task.get("taskArn") == arn and task.get("clusterArn") == cluster_arn
              and task.get("taskDefinitionArn") == definition, "Identidad de tarea inesperada")
        if task.get("lastStatus") == "STOPPED":
            runtime = task.get("containers", [])
            check(len(runtime) == 1 and runtime[0].get("name") == "migration", "Resultado sin contenedor migration unico")
            runtime = runtime[0]
            check(runtime.get("image") == image and runtime.get("imageDigest") == digest, "Imagen/digest ejecutado distinto o no verificable")
            check(type(runtime.get("exitCode")) is int and runtime["exitCode"] == 0, "Migracion fallida o sin exitCode=0")
            check(task.get("stopCode") == "EssentialContainerExited", "Tarea interrumpida o detenida por causa inesperada")
            emit(json.dumps({"event": "migration_completed", "taskArn": arn, "imageDigest": digest,
                             "exitCode": 0, "schemaVerified": False,
                             "logGroup": log_options.get("awslogs-group"),
                             "logStream": f"{log_options['awslogs-stream-prefix']}/migration/{arn.rsplit('/', 1)[-1]}"
                             if log_options.get("awslogs-stream-prefix") else None}))
            return
        sleep(min(5, max(0, deadline - clock())))
    raise MigrationError("Timeout: resultado incierto. Reconciliar taskArn/clientToken; no activar ni relanzar a ciegas")


def main():
    if len(sys.argv) > 1:
        print(__doc__, file=sys.stderr)
        return 0 if sys.argv[1:] == ["--help"] else 2

    def aws(service, operation, *args):
        command = ["aws", service, operation, *args, "--region", os.environ.get("AWS_REGION", "us-east-1"),
                   "--output", "json", "--no-cli-pager", "--cli-connect-timeout", "10", "--cli-read-timeout", "20"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=35, check=True)
            data = json.loads(result.stdout)
            check(isinstance(data, dict), "Respuesta AWS invalida")
            return data
        except (subprocess.SubprocessError, OSError, ValueError):
            raise MigrationError(f"AWS {service} {operation} fallo o dio resultado incierto; no activar. Reconciliar el intento antes de reintentar") from None

    try:
        run_migration(aws, emit=lambda line: print(line, flush=True))
        return 0
    except MigrationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except (KeyError, TypeError, IndexError):
        print("ERROR: respuesta incompleta o invalida; resultado incierto, no activar", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
