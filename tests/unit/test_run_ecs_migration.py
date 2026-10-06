"""Contrato del lanzador; todas las respuestas AWS son simuladas."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("migration_launcher", ROOT / "scripts/run_ecs_migration.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
PREFIX = "arn:aws:ecs:us-east-1:123456789012:"
CLUSTER = PREFIX + "cluster/sagrilaft-staging"
DEFINITION = PREFIX + "task-definition/sagrilaft-staging-migration:42"
TASK = PREFIX + "task/sagrilaft-staging/abc123"
IMAGE = "123456789012.dkr.ecr.us-east-1.amazonaws.com/sagrilaft-staging-backend:release-new"
DIGEST = "sha256:" + "a" * 64


@pytest.fixture
def setup(monkeypatch):
    env = {
        "AWS_REGION": "us-east-1", "AWS_ACCOUNT_ID": "123456789012",
        "ECS_CLUSTER_NAME": "sagrilaft-staging", "ECS_MIGRATION_TASK_DEFINITION_ARN": DEFINITION,
        "ECS_SECURITY_GROUP_ID": "sg-123abc", "ECS_PRIVATE_SUBNET_IDS": "subnet-123abc,subnet-456def",
        "ECS_MIGRATION_EXPECTED_IMAGE": IMAGE, "ECS_MIGRATION_EXPECTED_DIGEST": DIGEST,
        "ECS_MIGRATION_CLIENT_TOKEN": "staging-release-new-attempt-1", "ECS_MIGRATION_TIMEOUT_SECONDS": "10",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return {
        "get-caller-identity": {"Account": "123456789012"},
        "describe-clusters": {"clusters": [{"clusterArn": CLUSTER, "status": "ACTIVE"}], "failures": []},
        "describe-task-definition": {"taskDefinition": {
            "taskDefinitionArn": DEFINITION, "status": "ACTIVE", "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"], "containerDefinitions": [{
                "name": "migration", "image": IMAGE,
                "environment": [{"name": "RUN_MODE", "value": "migrate"}, {"name": "GIT_SHA", "value": "release-new"}],
                "secrets": [{"name": "secret", "valueFrom": "DO-NOT-PRINT"}],
                "logConfiguration": {"options": {"awslogs-group": "/migration", "awslogs-region": "us-east-1", "awslogs-stream-prefix": "migration"}},
            }],
        }},
        "describe-images": {"imageDetails": [{"imageDigest": DIGEST}]},
        "run-task": {"tasks": [{"taskArn": TASK}], "failures": []},
        "describe-tasks": {"tasks": [{"taskArn": TASK, "clusterArn": CLUSTER, "taskDefinitionArn": DEFINITION,
                                       "lastStatus": "STOPPED", "stopCode": "EssentialContainerExited",
                                       "containers": [{"name": "migration", "image": IMAGE, "imageDigest": DIGEST, "exitCode": 0}]}], "failures": []},
    }


def execute(responses):
    calls, events = [], []
    now = [0]

    def aws(service, operation, *args):
        calls.append((service, operation, args))
        response = responses[operation]
        if isinstance(response, Exception):
            raise response
        if isinstance(response, list):
            return response.pop(0)
        return response

    def sleep(seconds):
        now[0] += seconds

    launcher.run_migration(aws, events.append, sleep, lambda: now[0])
    return calls, events


def test_success_preserves_identity_token_and_reports_only_safe_evidence(setup):
    calls, events = execute(setup)
    run = next(args for _, operation, args in calls if operation == "run-task")
    assert run[run.index("--client-token") + 1] == "staging-release-new-attempt-1"
    assert run[run.index("--task-definition") + 1] == DEFINITION
    assert run[run.index("--cluster") + 1] == CLUSTER
    network = json.loads(run[run.index("--network-configuration") + 1])["awsvpcConfiguration"]
    assert network["assignPublicIp"] == "DISABLED"
    assert network["subnets"] == ["subnet-123abc", "subnet-456def"]
    result = json.loads(events[-1])
    assert result["imageDigest"] == DIGEST and result["exitCode"] == 0
    assert result["schemaVerified"] is False
    assert result["logStream"] == "migration/migration/abc123"
    assert "DO-NOT-PRINT" not in "".join(events)
    assert not any(operation in ("update-service", "register-task-definition") for _, operation, _ in calls)


@pytest.mark.parametrize("case", ["account", "cluster", "definition", "image", "mode", "sha", "digest", "sidecar"])
def test_preflight_failure_never_launches(setup, case):
    definition = setup["describe-task-definition"]["taskDefinition"]
    container = definition["containerDefinitions"][0]
    if case == "account": setup["get-caller-identity"]["Account"] = "999999999999"
    if case == "cluster": setup["describe-clusters"]["clusters"][0]["status"] = "INACTIVE"
    if case == "definition": definition["taskDefinitionArn"] += "9"
    if case == "image": container["image"] = IMAGE + "-old"
    if case == "mode": container["environment"][0]["value"] = "server"
    if case == "sha": container["environment"][1]["value"] = "old"
    if case == "digest": setup["describe-images"]["imageDetails"][0]["imageDigest"] = "sha256:" + "b" * 64
    if case == "sidecar": definition["containerDefinitions"].append({"name": "unexpected"})
    setup["run-task"] = AssertionError("No debe lanzar")
    with pytest.raises(launcher.MigrationError):
        execute(setup)


@pytest.mark.parametrize("variable,value", [
    ("AWS_ACCOUNT_ID", ""), ("ECS_MIGRATION_EXPECTED_DIGEST", ""),
    ("ECS_MIGRATION_CLIENT_TOKEN", ""), ("ECS_MIGRATION_CLIENT_TOKEN", "bad token"),
    ("ECS_MIGRATION_TASK_DEFINITION_ARN", PREFIX + "task-definition/name"),
    ("ECS_PRIVATE_SUBNET_IDS", "subnet-123, invalid"), ("ECS_MIGRATION_TIMEOUT_SECONDS", "0"),
    ("ECS_MIGRATION_TIMEOUT_SECONDS", "not-a-number"),
    ("ECS_MIGRATION_EXPECTED_IMAGE", IMAGE.rsplit(":", 1)[0] + ":bootstrap-placeholder"),
])
def test_bad_input_makes_no_aws_calls(setup, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    setup["get-caller-identity"] = AssertionError("No AWS calls expected")
    with pytest.raises(launcher.MigrationError):
        execute(setup)


@pytest.mark.parametrize("response", [{"failures": [{"reason": "capacity"}], "tasks": []},
                                      {"tasks": []}, {"tasks": [{}]}])
def test_run_task_failures_or_missing_arn_are_not_success(setup, response):
    setup["run-task"] = response
    with pytest.raises(launcher.MigrationError):
        execute(setup)


@pytest.mark.parametrize("field,value", [("exitCode", 1), ("exitCode", None), ("exitCode", False),
                                         ("imageDigest", None), ("imageDigest", "wrong"), ("image", "wrong")])
def test_stopped_is_not_success_without_verified_container(setup, field, value):
    setup["describe-tasks"]["tasks"][0]["containers"][0][field] = value
    with pytest.raises(launcher.MigrationError):
        execute(setup)


@pytest.mark.parametrize("field,value", [("clusterArn", "wrong"), ("taskDefinitionArn", "wrong"),
                                         ("stopCode", "UserInitiated"), ("containers", [])])
def test_wrong_task_or_interruption_is_rejected(setup, field, value):
    setup["describe-tasks"]["tasks"][0][field] = value
    with pytest.raises(launcher.MigrationError):
        execute(setup)


def test_eventual_consistency_then_running_then_success(setup):
    stopped = setup["describe-tasks"]
    running = copy.deepcopy(stopped)
    running["tasks"][0]["lastStatus"] = "RUNNING"
    setup["describe-tasks"] = [{"tasks": [], "failures": [{"reason": "MISSING"}]}, running, stopped]
    # Need more than the two polling intervals before STOPPED.
    os.environ["ECS_MIGRATION_TIMEOUT_SECONDS"] = "20"
    calls, _ = execute(setup)
    assert sum(operation == "run-task" for _, operation, _ in calls) == 1
    assert sum(operation == "describe-tasks" for _, operation, _ in calls) == 3


@pytest.mark.parametrize("missing", [False, True])
def test_timeout_does_not_relaunch_or_claim_success(setup, missing):
    if missing:
        setup["describe-tasks"] = {"tasks": [], "failures": [{"reason": "MISSING"}]}
    else:
        setup["describe-tasks"]["tasks"][0]["lastStatus"] = "RUNNING"
    with pytest.raises(launcher.MigrationError, match="Timeout.*incierto"):
        execute(setup)


@pytest.mark.parametrize("operation", ["run-task", "describe-tasks"])
def test_aws_errors_after_preflight_propagate_without_success(setup, operation):
    setup[operation] = launcher.MigrationError("AWS resultado incierto")
    with pytest.raises(launcher.MigrationError, match="incierto"):
        execute(setup)


def test_partial_launch_failure_preserves_arn_for_reconciliation(setup):
    setup["run-task"]["failures"] = [{"reason": "unknown"}]
    events = []
    with pytest.raises(launcher.MigrationError, match="incierto"):
        launcher.run_migration(lambda service, operation, *args: setup[operation], events.append)
    assert any(json.loads(event).get("taskArn") == TASK for event in events)
    assert all(json.loads(event)["event"] != "migration_completed" for event in events)


def test_describe_failure_other_than_missing_stops_polling(setup):
    setup["describe-tasks"] = {"tasks": [], "failures": [{"reason": "ACCESS_DENIED"}]}
    with pytest.raises(launcher.MigrationError, match="incierto"):
        execute(setup)


def test_shell_entrypoint_uses_cli_and_propagates_failure_without_leaking_output(setup, tmp_path, monkeypatch):
    executable = tmp_path / "aws"
    executable.write_text("#!/bin/sh\necho DO-NOT-PRINT >&2\nexit 23\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    result = subprocess.run(["bash", str(ROOT / "scripts/run_ecs_migration.sh")], capture_output=True, text=True)
    assert result.returncode != 0
    assert "get-caller-identity" in result.stderr
    assert "DO-NOT-PRINT" not in result.stdout + result.stderr


def test_shell_entrypoint_success_with_fake_aws(setup, tmp_path, monkeypatch):
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps(setup))
    executable = tmp_path / "aws"
    executable.write_text("#!/usr/bin/env python3\nimport json, sys\n"
                          f"data = json.load(open({str(responses)!r}))\n"
                          "print(json.dumps(data[sys.argv[2]]))\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    result = subprocess.run(["bash", str(ROOT / "scripts/run_ecs_migration.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["event"] == "migration_completed"
