import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "p20_reconcile", ROOT / "scripts/reconcile_p20_migration.py")
reconciler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconciler)

ENV = "p20-a1b2c3d4e5f6"
ACCOUNT = "123456789012"
REGION = "us-east-1"
CLUSTER_NAME = f"sagrilaft-{ENV}"
CLUSTER_ARN = f"arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/{CLUSTER_NAME}"
TASK_ARN = f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/{CLUSTER_NAME}/abc123"
DEFINITION = f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{CLUSTER_NAME}-migration:42"
IMAGE = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/sagrilaft-{ENV}-backend:release-new"
DIGEST = "sha256:" + "a" * 64


@pytest.fixture
def evidence():
    return [
        {"event": "migration_request", "clusterArn": CLUSTER_ARN,
         "taskDefinitionArn": DEFINITION, "image": IMAGE, "expectedDigest": DIGEST,
         "clientTokenSha256": "a" * 64, "logGroup": "/p20/migration",
         "logRegion": REGION, "logStreamPrefix": "migration"},
        {"event": "migration_launched", "taskArn": TASK_ARN},
    ]


def test_reconciler_only_describes_existing_task_and_whitelists_safe_logs(evidence):
    calls = []

    def aws(service, operation, *args):
        calls.append((service, operation, args))
        if operation == "describe-tasks":
            return {"tasks": [{"taskArn": TASK_ARN, "clusterArn": CLUSTER_ARN,
                               "taskDefinitionArn": DEFINITION, "lastStatus": "STOPPED",
                               "stopCode": "EssentialContainerExited", "stoppedReason": "ignored",
                               "containers": [{"name": "migration", "exitCode": 42,
                                               "imageDigest": DIGEST, "reason": "ignored"}]}],
                    "failures": []}
        return {"events": [{"message": '{"event":"p20_migration_fault","stage":"before_ddl",'
                                         '"runId":"p20-a1b2c3d4e5f6","databaseTouched":false,'
                                         '"secret":"must-not-escape"}'}]}

    result = reconciler.summarize(aws, evidence)
    assert [operation for _, operation, _ in calls] == ["describe-tasks", "get-log-events"]
    assert result["relaunchPerformed"] is False
    assert result["taskStatus"] == "STOPPED" and result["containerExitCode"] == 42
    assert result["imageDigestMatches"] is True
    assert result["faultMarkers"] == [{"event": "p20_migration_fault", "stage": "before_ddl",
                                      "runId": ENV, "databaseTouched": False}]


@pytest.mark.parametrize("mutation", [
    lambda events: events[0].update(clusterArn="arn:aws:ecs:us-east-1:123456789012:cluster/sagrilaft-prod"),
    lambda events: events[1].update(taskArn="arn:aws:ecs:us-east-1:123456789012:task/sagrilaft-prod/abc"),
    lambda events: events[1].update(taskArn="arn:aws:ecs:us-east-1:123456789012:task/sagrilaft-p20-ffffffffffff/abc"),
])
def test_reconciler_refuses_non_p20_or_mismatched_task_before_aws(evidence, mutation):
    mutation(evidence)
    with pytest.raises(reconciler.ReconcileError):
        reconciler.summarize(lambda *args: pytest.fail("No AWS calls expected"), evidence)


def test_reconciler_requires_launch_evidence_and_never_relaunches(evidence):
    evidence.pop()
    with pytest.raises(reconciler.ReconcileError, match="un único request y taskArn"):
        reconciler.summarize(lambda *args: pytest.fail("No AWS calls expected"), evidence)
