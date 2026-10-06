"""Orquestador probado sin AWS, CDK, contenedores ni bases de datos reales."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import deploy_release as release


def plan():
    return {"environment": "staging", "account": "123456789012", "region": "us-east-1",
            "mode": "compatible", "previous_tag": "old", "candidate_tag": "a" * 40,
            "desired_count": 1, "expected_head": "head2", "previous_revisions": ["head1"],
            "digests": {k: "sha256:" + "a" * 64 for k in release.SERVICES},
            "smoke_command": ["approved-smoke"], "context": {k: "configured" for k in (
                "hostedZoneName", "hostedZoneId", "domainName", "portalDomainName", "keycloakDomainName",
                "certificateArn", "bedrockModelId", "zohoSecretYaExiste", "proveedorListasCautela",
                "habilitarNatEgress", "snsAlertasSub")}}


def template(service_tag="old", migration_tag="old", count=1):
    resources = {}
    for name in [*release.SERVICES, "migration"]:
        tag = migration_tag if name == "migration" else service_tag
        resources[name] = {"Type": "AWS::ECS::TaskDefinition", "Properties": {
            "ContainerDefinitions": [{"Name": name, "Image": "repo:" + tag,
                                       "Environment": [{"Name": "GIT_SHA", "Value": tag}]}]}}
    resources["service"] = {"Type": "AWS::ECS::Service", "Properties": {"DesiredCount": count}}
    resources["db"] = {"Type": "AWS::RDS::DBInstance", "Properties": {"BackupRetentionPeriod": 7}}
    return {"Resources": resources, "Outputs": {"EcsMigrationImageTag": {"Value": migration_tag},
                                                 "EcsDesiredCount": {"Value": str(count)}}}


class FakeRuntime:
    def __init__(self, directory):
        self.plan, self.directory = plan(), directory
        self.stack = "SagrilaftStack-staging"
        self.calls, self.events, self.saved, self.deployments = [], [], {}, []
        self.current = template()
        self.account = self.plan["account"]
        self.fail = None
        self.locked = False
        self.mutable = False
        self.bad_digest = False
        self.schema = True
        self.lock_lost = False
        self.app_env = "staging"
        self.bad_db = False
        self.bad_diff = False
        self.smoked = False
        self.migration_calls = 0
        self.fail_migration = False
        self.out = {"EcsDesiredCount": "1", "EcsClusterName": "sagrilaft-staging",
                    "S3Bucket": "uploads", "EcsMigrationTaskDefinitionArn": "migration:2",
                    "EcsMigrationImageTag": "old", "RdsEndpoint": "db.internal", "KeycloakDbName": "sagrilaft",
                    "DbSecretArn": "arn:db-secret", "RuntimeConfigPrefix": "/sagrilaft/staging/config/",
                    "EcsSecurityGroupId": "sg-123"}
        for name, output in release.SERVICES.items():
            self.out[output] = name
            self.out[release.REPOS[name]] = f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{name}"

    def event(self, value): self.events.append(value)
    def save(self, name, value): self.saved[name] = copy.deepcopy(value)

    def synth(self, phase, service_tag, migration_tag, count):
        result = template(service_tag, migration_tag, count)
        if self.bad_diff:
            result["Resources"]["db"]["Properties"]["BackupRetentionPeriod"] = 1
        self.saved[phase] = result
        return copy.deepcopy(result)

    def deploy(self, phase):
        self.deployments.append(phase)
        if self.fail == phase:
            raise release.MigrationError("deploy fallido")
        self.current = copy.deepcopy(self.saved[phase])
        self.out["EcsMigrationImageTag"] = self.plan["candidate_tag"]
        self.out["EcsDesiredCount"] = self.current["Outputs"]["EcsDesiredCount"]["Value"]

    def smoke(self):
        self.smoked = True
        if self.fail == "smoke": raise release.MigrationError("smoke fallido")

    def aws(self, service, operation, *args):
        self.calls.append((service, operation, args))
        if self.fail == operation: raise release.MigrationError("AWS incierto")
        if operation == "get-caller-identity": return {"Account": self.account}
        if operation == "describe-stacks":
            return {"Stacks": [{"StackStatus": "UPDATE_COMPLETE",
                                "StackId": f"arn:aws:cloudformation:us-east-1:123456789012:stack/{self.stack}/123",
                                "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in self.out.items()]}]}
        if operation == "get-template": return {"TemplateBody": copy.deepcopy(self.current)}
        if operation == "list-tasks":
            name = args[args.index("--service-name") + 1]
            return {"taskArns": [name] if self.out["EcsDesiredCount"] != "0" else []}
        if operation == "describe-tasks":
            names = args[args.index("--tasks") + 1:]
            return {"tasks": [{"taskArn": name, "taskDefinitionArn": name, "lastStatus": "RUNNING",
                               "containers": [{"image": self.out[release.REPOS[name]] + ":" + self.current["Resources"][name]["Properties"]["ContainerDefinitions"][0]["Environment"][0]["Value"],
                                               "imageDigest": self.plan["digests"][name]}]} for name in names]}
        if operation == "describe-services":
            names = args[args.index("--services") + 1:]
            return {"services": [{"serviceName": name, "status": "ACTIVE", "pendingCount": 0,
                                  "runningCount": int(self.out["EcsDesiredCount"]), "desiredCount": int(self.out["EcsDesiredCount"]),
                                  "deployments": [{"rolloutState": "COMPLETED"}], "taskDefinition": name,
                                  "networkConfiguration": {"awsvpcConfiguration": {"securityGroups": ["sg-123"], "subnets": ["subnet-123"]}}}
                                 for name in names], "failures": []}
        if operation == "describe-task-definition":
            name = args[args.index("--task-definition") + 1]
            if name != self.out["EcsMigrationTaskDefinitionArn"]:
                tag = self.current["Resources"][name]["Properties"]["ContainerDefinitions"][0]["Environment"][0]["Value"]
                return {"taskDefinition": {"containerDefinitions": [{"image": self.out[release.REPOS[name]] + ":" + tag}]}}
            return {"taskDefinition": {"containerDefinitions": [{"environment": [
                {"name": "DATABASE_HOST", "value": "other" if self.bad_db else "db.internal"},
                {"name": "DATABASE_NAME", "value": "sagrilaft"}], "secrets": [
                    {"name": "DB_USER", "valueFrom": "arn:db-secret:username::"},
                    {"name": "DB_PASSWORD", "valueFrom": "arn:db-secret:password::"},
                    {"name": "APP_ENV", "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/sagrilaft/staging/config/APP_ENV"}]}]}}
        if operation == "describe-repositories": return {"repositories": [{"imageTagMutability": "MUTABLE" if self.mutable else "IMMUTABLE"}]}
        if operation == "describe-images": return {"imageDetails": [{"imageDigest": "bad" if self.bad_digest else "sha256:" + "a" * 64}]}
        if operation == "get-parameter": return {"Parameter": {"Value": self.app_env}}
        if operation == "put-object":
            assert args[args.index("--if-none-match") + 1] == "*"
            if self.locked: raise release.MigrationError("Lock ocupado")
            self.locked = True
            return {"ETag": "owned"}
        if operation == "head-object": return {"ETag": "other" if self.lock_lost else "owned"}
        if operation == "delete-object":
            assert args[args.index("--if-match") + 1] == "owned"
            self.locked = False
            return {}
        if operation == "get-log-events":
            events = [{"event": "migration_before", "revisions": ["head1"], "expectedHead": "head2"},
                      {"event": "migration_schema_verified", "revisions": ["head2"], "expectedHead": "head2"}]
            if not self.schema: events[1]["revisions"] = ["wrong"]
            return {"events": [{"message": json.dumps(event)} for event in events]}
        raise AssertionError((service, operation, args))


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    rt = FakeRuntime(tmp_path)
    def migration(aws, emit):
        rt.migration_calls += 1
        if rt.fail_migration: raise release.MigrationError("Migración fallida")
        emit(json.dumps({"event": "migration_completed", "taskArn": "task/123", "imageDigest": rt.plan["digests"]["backend"],
                         "schemaVerified": False, "logGroup": "/migration", "logStream": "migration/migration/123"}))
    monkeypatch.setattr(release, "run_migration", migration)
    return rt


def test_check_has_no_aws_mutations(runtime):
    release.coordinate(runtime)
    assert runtime.deployments == [] and runtime.migration_calls == 0 and not runtime.locked
    assert all(op not in ("put-object", "delete-object", "run-task") for _, op, _ in runtime.calls)


def test_compatible_sequence_and_release_lock(runtime):
    release.coordinate(runtime, True)
    assert runtime.deployments == ["prepare", "activate"]
    assert runtime.migration_calls == 1 and runtime.smoked and not runtime.locked
    assert runtime.saved["schema-evidence.json"]["schemaVerified"] is True
    assert runtime.events[-1]["event"] == "release_completed"


def test_bootstrap_keeps_zero_until_after_migration(runtime):
    runtime.plan["mode"] = "bootstrap"
    runtime.out["EcsDesiredCount"] = "0"
    runtime.current = template(count=0)
    release.coordinate(runtime, True)
    assert runtime.saved["prepare"]["Resources"]["service"]["Properties"]["DesiredCount"] == 0
    assert runtime.saved["activate"]["Resources"]["service"]["Properties"]["DesiredCount"] == 1


@pytest.mark.parametrize("field,value", [("account", "999999999999"), ("mutable", True), ("bad_digest", True), ("bad_diff", True)])
def test_preflight_failure_never_mutates(runtime, field, value):
    setattr(runtime, field, value)
    with pytest.raises(release.MigrationError): release.coordinate(runtime, True)
    assert runtime.deployments == [] and not runtime.locked and runtime.migration_calls == 0


def test_competing_run_cannot_acquire_lock(runtime):
    runtime.locked = True
    with pytest.raises(release.MigrationError, match="Lock ocupado"): release.coordinate(runtime, True)
    assert runtime.deployments == [] and runtime.migration_calls == 0 and runtime.locked


@pytest.mark.parametrize("field,value", [("fail", "prepare"), ("fail_migration", True),
                                         ("schema", False), ("bad_db", True), ("app_env", "production"),
                                         ("lock_lost", True)])
def test_failure_blocks_activation_and_retains_lock(runtime, field, value):
    setattr(runtime, field, value)
    with pytest.raises(release.MigrationError): release.coordinate(runtime, True)
    assert "activate" not in runtime.deployments
    assert runtime.locked and not runtime.smoked


@pytest.mark.parametrize("failure", ["activate", "smoke", "delete-object"])
def test_late_failure_is_not_reported_complete(runtime, failure):
    runtime.fail = failure
    with pytest.raises(release.MigrationError): release.coordinate(runtime, True)
    assert runtime.locked and all(e["event"] != "release_completed" for e in runtime.events)


@pytest.mark.parametrize("change", ["mode", "sha", "context", "smoke", "digests"])
def test_rejects_incomplete_or_unsafe_plans(change):
    p = plan()
    if change == "mode": p["mode"] = "incompatible"
    if change == "sha": p["candidate_tag"] = "latest"
    if change == "context": p["context"]["imageTag"] = "override"
    if change == "smoke": p["smoke_command"] = []
    if change == "digests": del p["digests"]["keycloak"]
    with pytest.raises(release.MigrationError): release.validate_plan(p)


@pytest.mark.parametrize("kind", ["service_image", "command", "db", "capacity", "output"])
def test_prepare_diff_rejects_unrelated_changes(kind):
    before = template()
    after = template(migration_tag="new")
    if kind == "service_image": after["Resources"]["backend"]["Properties"]["ContainerDefinitions"][0]["Image"] = "new"
    if kind == "command": after["Resources"]["migration"]["Properties"]["ContainerDefinitions"][0]["Command"] = ["bad"]
    if kind == "db": after["Resources"]["db"]["Properties"]["BackupRetentionPeriod"] = 0
    if kind == "capacity": after["Resources"]["service"]["Properties"]["DesiredCount"] = 2
    if kind == "output": after["Outputs"]["other"] = {"Value": "new"}
    with pytest.raises(release.MigrationError): release.assert_transition(before, after, "prepare")


def test_missing_schema_logs_fail_after_bounded_wait(runtime):
    now = [0]
    runtime.aws = lambda *args: {"events": []}
    with pytest.raises(release.MigrationError, match="evidencia suficiente"):
        release.schema_evidence(runtime, {"logGroup": "g", "logStream": "s"},
                                sleep=lambda n: now.__setitem__(0, now[0] + n), clock=lambda: now[0])
    assert now[0] == 60


def test_initial_revision_mismatch_blocks_activation(runtime):
    runtime.plan["previous_revisions"] = ["unexpected"]
    with pytest.raises(release.MigrationError, match="inicial"): release.coordinate(runtime, True)
    assert runtime.deployments == ["prepare"] and runtime.locked


def test_bootstrap_allows_scaling_and_cdk_telemetry_only():
    before = template(migration_tag="new", count=0)
    after = template(service_tag="new", migration_tag="new", count=2)
    before["Resources"]["CDKMetadata"] = {"Type": "AWS::CDK::Metadata", "Properties": {"Analytics": "old"}}
    after["Resources"]["CDKMetadata"] = {"Type": "AWS::CDK::Metadata", "Properties": {"Analytics": "new"}}
    after["Resources"]["scaling"] = {"Type": "AWS::ApplicationAutoScaling::ScalableTarget", "Properties": {"MinCapacity": 2}}
    release.assert_transition(before, after, "activate", bootstrap=True)
    with pytest.raises(release.MigrationError):
        release.assert_transition(before, after, "activate", bootstrap=False)


def test_changed_stack_after_lock_prevents_deploy(runtime):
    original = runtime.aws
    reads = [0]
    def aws(service, operation, *args):
        result = original(service, operation, *args)
        if operation == "get-template":
            reads[0] += 1
            if reads[0] == 2:
                result["TemplateBody"]["Resources"]["db"]["Properties"]["BackupRetentionPeriod"] = 3
        return result
    runtime.aws = aws
    with pytest.raises(release.MigrationError, match="cambió"):
        release.coordinate(runtime, True)
    assert runtime.deployments == [] and runtime.locked


def test_real_launcher_failure_through_orchestrator_does_not_activate(runtime, monkeypatch):
    # Reutiliza el lanzador real; AWS sigue siendo FakeRuntime. Falla en preflight
    # por el ARN sintético, antes de que pueda lanzar una tarea.
    import run_ecs_migration
    monkeypatch.setattr(release, "run_migration", run_ecs_migration.run_migration)
    with pytest.raises(release.MigrationError):
        release.coordinate(runtime, True)
    assert runtime.deployments == ["prepare"] and runtime.locked


@pytest.mark.parametrize("exit_code", [0, 7])
def test_orchestrator_with_real_launcher_and_fake_aws(runtime, monkeypatch, exit_code):
    import run_ecs_migration
    prefix = "arn:aws:ecs:us-east-1:123456789012:"
    definition = prefix + "task-definition/staging-migration:42"
    task = prefix + "task/sagrilaft-staging/migration123"
    cluster = prefix + "cluster/sagrilaft-staging"
    runtime.out["EcsMigrationTaskDefinitionArn"] = definition
    original = runtime.aws
    def aws(service, operation, *args):
        if operation == "describe-clusters":
            return {"clusters": [{"clusterArn": cluster, "status": "ACTIVE"}]}
        if operation == "run-task":
            runtime.migration_calls += 1
            assert args[args.index("--task-definition") + 1] == definition
            return {"tasks": [{"taskArn": task}]}
        if operation == "describe-tasks" and task in args:
            return {"tasks": [{"taskArn": task, "taskDefinitionArn": definition, "clusterArn": cluster,
                               "lastStatus": "STOPPED", "stopCode": "EssentialContainerExited",
                               "containers": [{"name": "migration", "image": runtime.out["EcrBackendUri"] + ":" + runtime.plan["candidate_tag"],
                                               "imageDigest": runtime.plan["digests"]["backend"], "exitCode": exit_code}]}]}
        result = original(service, operation, *args)
        if operation == "describe-task-definition" and definition in args:
            data = result["taskDefinition"]
            data.update(taskDefinitionArn=definition, status="ACTIVE", networkMode="awsvpc", requiresCompatibilities=["FARGATE"])
            container = data["containerDefinitions"][0]
            container.update(name="migration", image=runtime.out["EcrBackendUri"] + ":" + runtime.plan["candidate_tag"],
                             logConfiguration={"options": {"awslogs-group": "/migration", "awslogs-stream-prefix": "migration"}})
            container["environment"] += [{"name": "RUN_MODE", "value": "migrate"}, {"name": "GIT_SHA", "value": runtime.plan["candidate_tag"]}]
        return result
    runtime.aws = aws
    monkeypatch.setattr(release, "run_migration", run_ecs_migration.run_migration)
    if exit_code:
        with pytest.raises(release.MigrationError, match="exitCode"):
            release.coordinate(runtime, True)
        assert runtime.deployments == ["prepare"] and runtime.locked
    else:
        release.coordinate(runtime, True)
        assert runtime.deployments == ["prepare", "activate"] and not runtime.locked
    assert runtime.migration_calls == 1
