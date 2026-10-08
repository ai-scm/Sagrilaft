#!/usr/bin/env python3
"""Read-only reconciliation of a previously launched P20 ECS migration task.

This utility deliberately has no RunTask, UpdateService, CloudFormation deploy,
or S3 lock operation. It requires the launch evidence and only describes that
task and reads its CloudWatch log stream.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class ReconcileError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ReconcileError(message)


def summarize(aws, events):
    requests = [event for event in events if event.get("event") == "migration_request"]
    launched = [event for event in events if event.get("event") == "migration_launched"]
    require(len(requests) == 1 and len(launched) == 1,
            "Evidencia debe identificar un único request y taskArn; no se relanza")
    request, launch = requests[0], launched[0]
    match = re.fullmatch(r"arn:aws:ecs:([a-z0-9-]+):(\d{12}):cluster/(sagrilaft-(p20-[a-f0-9]{12}))",
                         request.get("clusterArn", ""))
    require(match is not None, "El cluster de evidencia no es un cluster P20 válido")
    region, account, cluster_name, environment = match.groups()
    log_region = request.get("logRegion") or region
    require(log_region == region, "Los logs de reconciliación deben estar en la región del cluster")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", request.get("clientTokenSha256", ""))),
            "La evidencia no incluye huella válida del client token")
    task_prefix = f"arn:aws:ecs:{region}:{account}:task/{cluster_name}/"
    task_arn = launch.get("taskArn", "")
    require(task_arn.startswith(task_prefix), "taskArn no pertenece al cluster P20 del request")
    definition = request.get("taskDefinitionArn", "")
    image_match = re.fullmatch(
        rf"{account}\.dkr\.ecr\.{region}\.amazonaws\.com/sagrilaft-{re.escape(environment)}-backend:[A-Za-z0-9_][A-Za-z0-9_.-]{{0,127}}",
        request.get("image", ""))
    require(bool(image_match), "La imagen no pertenece al repositorio backend P20")
    require(bool(re.fullmatch(r"sha256:[a-f0-9]{64}", request.get("expectedDigest", ""))),
            "Falta digest esperado válido")

    response = aws("ecs", "describe-tasks", "--cluster", request["clusterArn"], "--tasks", task_arn,
                   "--region", region)
    require(not response.get("failures") and len(response.get("tasks", [])) == 1,
            "ECS no permite reconciliar de forma inequívoca la tarea")
    task = response["tasks"][0]
    require(task.get("taskArn") == task_arn and task.get("clusterArn") == request["clusterArn"]
            and task.get("taskDefinitionArn") == definition, "Identidad de tarea distinta a la evidencia")
    containers = task.get("containers", [])
    require(len(containers) == 1 and containers[0].get("name") == "migration",
            "La tarea no tiene exactamente el contenedor migration esperado")
    container = containers[0]

    safe_markers = []
    group = request.get("logGroup")
    prefix = request.get("logStreamPrefix")
    if group and prefix:
        stream = f"{prefix}/migration/{task_arn.rsplit('/', 1)[-1]}"
        try:
            page = aws("logs", "get-log-events", "--log-group-name", group,
                       "--log-stream-name", stream, "--start-from-head", "--limit", "100",
                       "--region", log_region)
            for entry in page.get("events", []):
                try:
                    value = json.loads(entry.get("message", ""))
                except (ValueError, TypeError):
                    continue
                if value.get("event") in ("p20_migration_fault", "migration_before",
                                          "migration_schema_verified"):
                    # Whitelist safe evidence fields; never copy arbitrary log text.
                    safe_markers.append({key: value[key] for key in
                                         ("event", "stage", "runId", "databaseTouched",
                                          "revisions", "expectedHead") if key in value})
        except ReconcileError:
            raise

    return {
        "environment": environment,
        "taskArn": task_arn,
        "taskStatus": task.get("lastStatus"),
        "stopCode": task.get("stopCode"),
        "stoppedReasonPresent": bool(task.get("stoppedReason")),
        "containerExitCode": container.get("exitCode"),
        "containerReasonPresent": bool(container.get("reason")),
        "imageDigestMatches": container.get("imageDigest") == request["expectedDigest"],
        "faultMarkers": safe_markers,
        "relaunchPerformed": False,
    }


def load_events(path):
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            require(isinstance(value, dict), "La evidencia JSONL debe contener objetos")
            events.append(value)
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, help="events.jsonl del intento aislado P20")
    args = parser.parse_args()

    def aws(service, operation, *cli_args):
        require((service, operation) in (("ecs", "describe-tasks"), ("logs", "get-log-events")),
                "Operación AWS no permitida por el reconciliador")
        region = os.environ.get("AWS_REGION", "us-east-1")
        region_args = [] if "--region" in cli_args else ["--region", region]
        command = ["aws", service, operation, *cli_args, *region_args,
                   "--output", "json", "--no-cli-pager", "--cli-connect-timeout", "10",
                   "--cli-read-timeout", "20"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=35, check=True)
            value = json.loads(result.stdout)
            require(isinstance(value, dict), "Respuesta AWS no estructurada")
            return value
        except (subprocess.SubprocessError, OSError, ValueError):
            raise ReconcileError("Consulta AWS de solo lectura falló; conservar evidencia y no relanzar") from None

    try:
        print(json.dumps(summarize(aws, load_events(args.evidence)), sort_keys=True))
        return 0
    except (ReconcileError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
