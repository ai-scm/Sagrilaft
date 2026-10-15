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


def p20_plan():
    p = plan()
    p['environment'] = 'p20-012345abcdef'
    p['context'].update({
        'hostedZoneName': '', 'hostedZoneId': '', 'snsAlertasSub': '',
        'habilitarNatEgress': False, 'proveedorListasCautela': 'dummy',
        'zohoSecretYaExiste': False, 'sesEmailOrigen': '',
    })
    return p


def test_p20_plan_requires_run_scoped_environment_and_isolated_context():
    p = p20_plan()
    p['p20_operation'] = 'rollback-services'
    p['previous_digests'] = {k: 'sha256:' + 'b' * 64 for k in release.SERVICES}
    release.validate_plan(p)
    for field, value in [
        ('environment', 'staging'),
        ('environment', 'p20-prod'),
    ]:
        unsafe = copy.deepcopy(p)
        unsafe[field] = value
        with pytest.raises(release.MigrationError):
            release.validate_plan(unsafe)


def test_p20_stopped_clone_repoint_plan_requires_zero_capacity_and_same_run_id():
    p = p20_plan()
    p['p20_operation'] = 'configure-restored-db-stopped'
    p['desired_count'] = 0
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    p['context']['databaseHostOverride'] = 'p20-012345abcdef-c7-test-20261012.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-c7-test-20261012'
    release.validate_plan(p)

    unsafe = copy.deepcopy(p)
    unsafe['desired_count'] = 1
    with pytest.raises(release.MigrationError, match='Capacidad inválida'):
        release.validate_plan(unsafe)

    unsafe = copy.deepcopy(p)
    unsafe['context']['restoredDbIdentifier'] = 'p20-fedcba654321-c7-test-20261012'
    with pytest.raises(release.MigrationError, match='identificador de RDS'):
        release.validate_plan(unsafe)

    fixed_backend = copy.deepcopy(p)
    fixed_backend.update({
        'backend_image_tag': '4d63c1356cc92b8d8d515e7147a7ac06565b0583',
        'backend_image_digest': 'sha256:' + 'c' * 64,
    })
    release.validate_plan(fixed_backend)

    unsafe = copy.deepcopy(fixed_backend)
    unsafe['backend_image_digest'] = None
    with pytest.raises(release.MigrationError, match='tag y digest juntos'):
        release.validate_plan(unsafe)

    unsafe = copy.deepcopy(fixed_backend)
    unsafe['environment'] = 'staging'
    with pytest.raises(release.MigrationError, match='override de imagen backend'):
        release.validate_plan(unsafe)


def backend_only_plan(count=1):
    p = p20_plan()
    p.update({
        'p20_operation': 'backend-only-restored-db',
        'desired_count': 0,
        'backend_desired_count': count,
        'backend_image_tag': '4d63c1356cc92b8d8d515e7147a7ac06565b0583',
        'backend_image_digest': 'sha256:' + 'c' * 64,
        'preflightOnly': True,
        'executionAuthorized': False,
    })
    p['context'].update({
        'databaseHostOverride': 'restore.p20.internal',
        'restoredDbIdentifier': 'p20-012345abcdef-c7-test-20261012',
        'backendMaxCapacity': 1,
    })
    return p


def backend_only_templates(host='restore.p20.internal', tag='4d63c1356cc92b8d8d515e7147a7ac06565b0583'):
    task_names = [*release.SERVICES, 'migration']
    resources = {}
    task_ids = {}
    for name in task_names:
        container_name = {'formulario-publico': 'frontend', 'portal-interno': 'portal'}.get(name, name)
        task_id = 'task-' + name
        task_ids[name] = task_id
        if container_name == 'backend':
            env = {'GIT_SHA': tag, 'DATABASE_HOST': host,
                   'KEYCLOAK_DB_URL': f'jdbc:postgresql://{host}:5432/sagrilaft',
                   'P20_RUN_ID': 'p20-012345abcdef', 'ZOHO_SIGN_ENABLED': 'false'}
        elif container_name == 'keycloak':
            env = {'KC_DB_URL': f'jdbc:postgresql://{host}:5432/sagrilaft'}
        elif container_name == 'migration':
            env = {'GIT_SHA': 'candidate', 'DATABASE_HOST': host,
                   'KEYCLOAK_DB_URL': f'jdbc:postgresql://{host}:5432/sagrilaft',
                   'P20_RUN_ID': 'p20-012345abcdef', 'ZOHO_SIGN_ENABLED': 'false'}
        else:
            env = {'GIT_SHA': 'baseline'}
        image_tag = tag if container_name == 'backend' else ('candidate' if container_name == 'migration' else 'baseline')
        resources[task_id] = {'Type': 'AWS::ECS::TaskDefinition', 'Properties': {
            'ContainerDefinitions': [{'Name': container_name, 'Image': 'repo:' + image_tag,
                                     'Environment': [{'Name': k, 'Value': v} for k, v in env.items()],
                                     'Secrets': [{'Name': 'DB_PASSWORD', 'ValueFrom': 'p20-secret'}]}]}}
    for name in release.SERVICES:
        resources['service-' + name] = {'Type': 'AWS::ECS::Service', 'Properties': {
            'DesiredCount': 0, 'TaskDefinition': {'Ref': task_ids[name]}, 'Cluster': 'p20-cluster'}}
    outputs = {'EcsDesiredCount': {'Value': '0'}, 'EcsDatabaseHost': {'Value': host},
               'RdsEndpoint': {'Value': 'original.p20.internal'}}
    before = {'Resources': resources, 'Outputs': outputs}
    after = copy.deepcopy(before)
    after['Resources']['service-backend']['Properties']['DesiredCount'] = 1
    return before, after


def test_p20_backend_only_plan_requires_one_cloned_db_and_pinned_image():
    release.validate_plan(backend_only_plan(1))
    release.validate_plan(backend_only_plan(0))

    unsafe = backend_only_plan(2)
    with pytest.raises(release.MigrationError, match='backend_desired_count=0 o 1'):
        release.validate_plan(unsafe)

    unsafe = backend_only_plan()
    unsafe['desired_count'] = 1
    with pytest.raises(release.MigrationError, match='Capacidad inválida'):
        release.validate_plan(unsafe)

    unsafe = backend_only_plan()
    unsafe['backend_image_digest'] = None
    with pytest.raises(release.MigrationError, match='tag y digest juntos'):
        release.validate_plan(unsafe)

    unsafe = backend_only_plan()
    unsafe['context']['restoredDbIdentifier'] = 'p20-fedcba654321-c7-test-20261012'
    with pytest.raises(release.MigrationError, match='identificador de RDS'):
        release.validate_plan(unsafe)

    unsafe = backend_only_plan()
    unsafe['context']['backendMaxCapacity'] = 2
    with pytest.raises(release.MigrationError, match='backendMaxCapacity=1'):
        release.validate_plan(unsafe)


@pytest.mark.parametrize(('source_count', 'target_count'), [(0, 1), (1, 0)])
def test_p20_backend_only_transition_changes_only_backend_capacity(source_count, target_count):
    before, activated = backend_only_templates()
    after = activated if target_count == 1 else copy.deepcopy(activated)
    if target_count == 0:
        after['Resources']['service-backend']['Properties']['DesiredCount'] = 0
    release.assert_p20_backend_only_transition(
        before if source_count == 0 else activated, after, source_count, target_count,
        'restore.p20.internal', '4d63c1356cc92b8d8d515e7147a7ac06565b0583', 'p20-012345abcdef')


@pytest.mark.parametrize('mutation', [
    'frontend_count', 'frontend_image', 'portal_image', 'keycloak_image',
    'backend_image', 'db_host', 'zoho_enabled', 'extra_resource',
])
def test_p20_backend_only_transition_rejects_out_of_scope_changes(mutation):
    before, after = backend_only_templates()
    unsafe = copy.deepcopy(after)
    if mutation == 'frontend_count':
        unsafe['Resources']['service-formulario-publico']['Properties']['DesiredCount'] = 1
    elif mutation in ('frontend_image', 'portal_image', 'keycloak_image'):
        task_id = {'frontend_image': 'task-formulario-publico', 'portal_image': 'task-portal-interno',
                   'keycloak_image': 'task-keycloak'}[mutation]
        unsafe['Resources'][task_id]['Properties']['ContainerDefinitions'][0]['Image'] = 'repo:unexpected'
    elif mutation == 'backend_image':
        unsafe['Resources']['task-backend']['Properties']['ContainerDefinitions'][0]['Image'] = 'repo:wrong'
    elif mutation == 'db_host':
        env = unsafe['Resources']['task-backend']['Properties']['ContainerDefinitions'][0]['Environment']
        next(item for item in env if item['Name'] == 'DATABASE_HOST')['Value'] = 'original.p20.internal'
    elif mutation == 'zoho_enabled':
        env = unsafe['Resources']['task-backend']['Properties']['ContainerDefinitions'][0]['Environment']
        next(item for item in env if item['Name'] == 'ZOHO_SIGN_ENABLED')['Value'] = 'true'
    else:
        unsafe['Resources']['unexpected'] = {'Type': 'AWS::S3::Bucket', 'Properties': {}}
    with pytest.raises(release.MigrationError):
        release.assert_p20_backend_only_transition(
            before, unsafe, 0, 1, 'restore.p20.internal',
            '4d63c1356cc92b8d8d515e7147a7ac06565b0583', 'p20-012345abcdef')


@pytest.mark.parametrize('target_count', [0, 1])
def test_p20_backend_only_preflight_is_read_only_and_never_migrates(tmp_path, monkeypatch, target_count):
    p = backend_only_plan(target_count)
    outputs = {
        'EcsDesiredCount': '0', 'EcsDatabaseHost': 'restore.p20.internal',
        'RdsEndpoint': 'original.p20.internal', 'EcsMigrationImageTag': p['candidate_tag'],
        'EcsClusterName': 'sagrilaft-' + p['environment'], 'S3Bucket': 'p20-bucket',
        'EcsMigrationTaskDefinitionArn': 'migration:4',
        'EcsBackendTargetGroupArn': 'arn:target-group:backend',
    }
    outputs.update({key: p['environment'] + '-' + kind for kind, key in release.SERVICES.items()})
    before, activated = backend_only_templates()
    baseline = before if target_count == 1 else activated
    target = activated if target_count == 1 else before

    class Runtime:
        plan, stack = p, 'SagrilaftStack-' + p['environment']

        def __init__(self):
            self.directory, self.calls, self.saved, self.events, self.deployments = tmp_path, [], {}, [], []

        def aws(self, service, operation, *args):
            self.calls.append((service, operation, args))
            if (service, operation) == ('sts', 'get-caller-identity'):
                return {'Account': p['account']}
            pytest.fail(f'Unexpected AWS call during preflight: {service}/{operation}')

        def save(self, name, value): self.saved[name] = copy.deepcopy(value)
        def event(self, value): self.events.append(copy.deepcopy(value))
        def synth(self, phase, image_tag, migration_tag, count):
            assert phase == 'p20-backend-only-restored-db'
            assert image_tag == p['previous_tag'] and migration_tag == p['candidate_tag'] and count == 0
            return copy.deepcopy(target)
        def deploy(self, phase): self.deployments.append(phase)

    state_checks = []
    monkeypatch.setattr(release, 'stack_state', lambda _rt: outputs)
    monkeypatch.setattr(release, 'verify_restored_database', lambda *_args: {
        'identifier': p['context']['restoredDbIdentifier'], 'host': 'restore.p20.internal',
        'status': 'available', 'kmsKeyArn': 'arn:kms'})
    monkeypatch.setattr(release, 'verify_p20_clone_network_and_kms', lambda *_args: {'isolated': True})
    monkeypatch.setattr(release, 'verify_p20_backend_image', lambda *_args: state_checks.append('image-digest'))
    monkeypatch.setattr(release, 'verify_p20_backend_only_services',
                        lambda _rt, _outputs, count, *_args, **_kwargs: state_checks.append(('services', count)) or [])
    monkeypatch.setattr(release, 'deployed_template', lambda _rt: copy.deepcopy(baseline))

    rt = Runtime()
    release.coordinate(rt)
    assert rt.deployments == []
    assert rt.events[-1]['event'] == 'p20_backend_only_preflight_validated'
    assert rt.events[-1]['backendDesiredCountBefore'] == 1 - target_count
    assert rt.events[-1]['backendDesiredCountAfter'] == target_count
    assert rt.events[-1]['otherServicesRemainZero'] is True
    assert rt.events[-1]['migrationWillRun'] is False
    assert ('services', 1 - target_count) in state_checks
    assert all(operation not in {'put-object', 'delete-object', 'run-task', 'update-service'}
               for _, operation, _ in rt.calls)


def stopped_repoint_templates(source='primary.p20.internal', target='restore.p20.internal'):
    before = rollback_template('previous', migration_tag='candidate', count=0)
    before['Outputs'].update({
        'EcsDesiredCount': {'Value': '0'}, 'RdsEndpoint': {'Value': source},
        'EcsDatabaseHost': {'Value': source},
    })
    db_fields = {
        'backend': {'DATABASE_HOST': source, 'KEYCLOAK_DB_URL': f'jdbc:postgresql://{source}:5432/sagrilaft'},
        'keycloak': {'KC_DB_URL': f'jdbc:postgresql://{source}:5432/sagrilaft'},
        'migration': {'DATABASE_HOST': source, 'KEYCLOAK_DB_URL': f'jdbc:postgresql://{source}:5432/sagrilaft'},
    }
    for name, fields in db_fields.items():
        container = before['Resources'][name]['Properties']['ContainerDefinitions'][0]
        container['Environment'].extend({'Name': key, 'Value': value} for key, value in fields.items())
        if name in {'backend', 'migration'}:
            container['Environment'].extend([
                {'Name': 'P20_RUN_ID', 'Value': 'p20-012345abcdef'},
                {'Name': 'ZOHO_SIGN_ENABLED', 'Value': 'false'},
            ])
        container['Secrets'] = [{'Name': 'DB_PASSWORD', 'ValueFrom': 'p20-db-secret'}]
    after = copy.deepcopy(before)
    after['Outputs']['EcsDatabaseHost'] = {'Value': target}
    for name, fields in db_fields.items():
        container = after['Resources'][name]['Properties']['ContainerDefinitions'][0]
        for item in container['Environment']:
            if item['Name'] in fields:
                item['Value'] = target if item['Name'] == 'DATABASE_HOST' else f'jdbc:postgresql://{target}:5432/sagrilaft'
    return before, after


def test_p20_stopped_clone_repoint_transition_changes_only_db_endpoints():
    before, after = stopped_repoint_templates()
    release.assert_p20_stopped_database_transition(
        before, after, 'primary.p20.internal', 'restore.p20.internal', 'p20-012345abcdef')

    unsafe = copy.deepcopy(after)
    unsafe['Outputs']['EcsDesiredCount']['Value'] = '1'
    with pytest.raises(release.MigrationError, match='desiredCount=0'):
        release.assert_p20_stopped_database_transition(
            before, unsafe, 'primary.p20.internal', 'restore.p20.internal', 'p20-012345abcdef')


def test_p20_stopped_clone_backend_override_changes_only_backend_image():
    tag = '4d63c1356cc92b8d8d515e7147a7ac06565b0583'
    before, after = stopped_repoint_templates('restore.p20.internal', 'restore.p20.internal')
    backend = after['Resources']['backend']['Properties']['ContainerDefinitions'][0]
    backend['Image'] = '123456789012.dkr.ecr.us-east-1.amazonaws.com/backend:' + tag
    next(item for item in backend['Environment'] if item['Name'] == 'GIT_SHA')['Value'] = tag
    release.assert_p20_stopped_database_transition(
        before, after, 'restore.p20.internal', 'restore.p20.internal', 'p20-012345abcdef',
        backend_image_tag=tag)

    unsafe = copy.deepcopy(after)
    frontend = unsafe['Resources']['formulario-publico']['Properties']['ContainerDefinitions'][0]
    frontend['Image'] = '123456789012.dkr.ecr.us-east-1.amazonaws.com/frontend:' + tag
    with pytest.raises(release.MigrationError):
        release.assert_p20_stopped_database_transition(
            before, unsafe, 'restore.p20.internal', 'restore.p20.internal', 'p20-012345abcdef',
            backend_image_tag=tag)


def test_p20_stopped_clone_repoint_accepts_original_rds_intrinsics_from_cfn():
    before, after = stopped_repoint_templates()
    before['Resources']['DatabasePostgresA1'] = {'Type': 'AWS::RDS::DBInstance'}
    after['Resources']['DatabasePostgresA1'] = {'Type': 'AWS::RDS::DBInstance'}
    original_endpoint = {'Fn::GetAtt': ['DatabasePostgresA1', 'Endpoint.Address']}
    before['Outputs']['RdsEndpoint']['Value'] = original_endpoint
    after['Outputs']['RdsEndpoint']['Value'] = original_endpoint
    for name in ('backend', 'migration'):
        env = before['Resources'][name]['Properties']['ContainerDefinitions'][0]['Environment']
        for item in env:
            if item['Name'] == 'DATABASE_HOST':
                item['Value'] = {'Fn::GetAtt': ['DatabasePostgresA1', 'Endpoint.Address']}
            elif item['Name'] == 'KEYCLOAK_DB_URL':
                item['Value'] = {'Fn::Join': ['', [
                    'jdbc:postgresql://',
                    {'Fn::GetAtt': ['DatabasePostgresA1', 'Endpoint.Address']},
                    ':5432/sagrilaft',
                ]]}
    env = before['Resources']['keycloak']['Properties']['ContainerDefinitions'][0]['Environment']
    for item in env:
        if item['Name'] == 'KC_DB_URL':
            item['Value'] = {'Fn::Join': ['', [
                'jdbc:postgresql://',
                {'Fn::GetAtt': ['DatabasePostgresA1', 'Endpoint.Address']},
                ':5432/sagrilaft',
            ]]}
    release.assert_p20_stopped_database_transition(
        before, after, 'primary.p20.internal', 'restore.p20.internal', 'p20-012345abcdef')


def test_p20_stopped_clone_repoint_preflight_never_deploys_or_starts_tasks(tmp_path, monkeypatch):
    p = p20_plan()
    p.update({'p20_operation': 'configure-restored-db-stopped', 'desired_count': 0,
              'preflightOnly': True, 'executionAuthorized': False})
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    p['context'].update({
        'databaseHostOverride': 'restore.p20.internal',
        'restoredDbIdentifier': 'p20-012345abcdef-c7-test-20261012',
    })
    names = {kind: f'{p["environment"]}-{kind}' for kind in release.SERVICES}
    outputs = {
        'EcsDesiredCount': '0', 'EcsMigrationImageTag': p['candidate_tag'],
        'EcsClusterName': f'sagrilaft-{p["environment"]}', 'S3Bucket': 'p20-bucket',
        'EcsMigrationTaskDefinitionArn': 'migration:2', 'RdsEndpoint': 'primary.p20.internal',
        'EcsDatabaseHost': 'primary.p20.internal',
    }
    outputs.update({release.SERVICES[kind]: name for kind, name in names.items()})
    before, after = stopped_repoint_templates('primary.p20.internal', 'restore.p20.internal')

    class Runtime:
        plan, stack = p, 'SagrilaftStack-' + p['environment']

        def __init__(self):
            self.directory, self.calls, self.saved, self.events, self.deployments = tmp_path, [], {}, [], []

        def aws(self, service, operation, *args):
            self.calls.append((service, operation, args))
            if (service, operation) == ('sts', 'get-caller-identity'):
                return {'Account': p['account']}
            pytest.fail(f'Unexpected AWS call: {service}/{operation}')

        def save(self, name, value): self.saved[name] = copy.deepcopy(value)
        def event(self, value): self.events.append(copy.deepcopy(value))
        def synth(self, phase, image_tag, migration_tag, count):
            assert (phase, image_tag, migration_tag, count) == (
                'repoint-restored-db-stopped', p['previous_tag'], p['candidate_tag'], 0)
            return copy.deepcopy(after)
        def deploy(self, phase): self.deployments.append(phase)

    checks = []
    monkeypatch.setattr(release, 'stack_state', lambda _rt: outputs)
    monkeypatch.setattr(release, 'require_p20_services_stopped', lambda *_args: checks.append('stopped'))
    monkeypatch.setattr(release, 'verify_restored_database', lambda *_args: {
        'identifier': p['context']['restoredDbIdentifier'], 'host': 'restore.p20.internal',
        'status': 'available', 'kmsKeyArn': 'arn:kms'})
    monkeypatch.setattr(release, 'verify_p20_clone_network_and_kms', lambda *_args: {'postgresIngressFromEcsVerified': True})
    monkeypatch.setattr(release, 'verify_tag_digests', lambda *_args: checks.append('digests'))
    monkeypatch.setattr(release, 'deployed_template', lambda _rt: copy.deepcopy(before))
    monkeypatch.setattr(release, 'services', lambda *_args: [
        {'serviceName': names[kind], 'taskDefinition': f'{kind}:2'} for kind in release.SERVICES])
    monkeypatch.setattr(release, 'verify_p20_task_database_and_secret_scope',
                        lambda *_args, **kwargs: checks.append(('db-secret-scope', kwargs.get('before_host'))))

    runtime = Runtime()
    release.coordinate(runtime)
    assert runtime.deployments == []
    assert runtime.events[-1]['event'] == 'p20_restored_database_stopped_preflight_validated'
    assert runtime.events[-1]['desiredCount'] == 0
    assert runtime.events[-1]['servicesWillStart'] is False
    assert runtime.events[-1]['migrationWillRun'] is False
    assert checks == ['stopped', 'digests', ('db-secret-scope', 'primary.p20.internal')]
    assert all(operation not in {'put-object', 'delete-object', 'run-task', 'update-service'}
               for _, operation, _ in runtime.calls)

    with pytest.raises(release.MigrationError, match='no autoriza actualizar task definitions'):
        release.coordinate(runtime, execute=True)
    assert runtime.deployments == []
    assert all(operation not in {'put-object', 'delete-object', 'run-task', 'update-service'}
               for _, operation, _ in runtime.calls)

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['keycloak']['Properties']['ContainerDefinitions'][0]['Environment'][-1]['Value'] = 'jdbc:postgresql://prod.example:5432/sagrilaft'
    with pytest.raises(release.MigrationError, match='Conexión de destino incorrecta'):
        release.assert_p20_stopped_database_transition(
            before, unsafe, 'primary.p20.internal', 'restore.p20.internal', 'p20-012345abcdef')

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Secrets'][0]['ValueFrom'] = 'staging-db-secret'
    with pytest.raises(release.MigrationError, match='secretos'):
        release.assert_p20_stopped_database_transition(
            before, unsafe, 'primary.p20.internal', 'restore.p20.internal', 'p20-012345abcdef')
    for key, value in [('snsAlertasSub', 'someone@example.invalid'),
                       ('habilitarNatEgress', True), ('hostedZoneName', 'example.com')]:
        unsafe = copy.deepcopy(p)
        unsafe['context'][key] = value
        with pytest.raises(release.MigrationError):
            release.validate_plan(unsafe)


@pytest.mark.parametrize("fault", ["fail-before-ddl", "observer-loss-after-launch"])
def test_p20_migration_fault_modes_are_allowlisted(fault):
    p = p20_plan()
    p["p20_migration_fault"] = fault
    with pytest.raises(release.MigrationError, match="ruta exclusiva scenario-a-fixture"):
        release.validate_plan(p)

    p["environment"] = "staging"
    with pytest.raises(release.MigrationError, match="solo se permite en P20"):
        release.validate_plan(p)

    p = p20_plan()
    p["p20_migration_fault"] = "run-arbitrary-command"
    with pytest.raises(release.MigrationError, match="Modo de fallo de migración P20 inválido"):
        release.validate_plan(p)

    p = p20_plan()
    p["p20_migration_fault"] = fault
    p["p20_operation"] = "rollback-services"
    p["previous_digests"] = {key: "sha256:" + "b" * 64 for key in release.SERVICES}
    with pytest.raises(release.MigrationError, match="ruta exclusiva scenario-a-fixture"):
        release.validate_plan(p)


def test_p20_service_rollback_plan_requires_four_previous_digests():
    p = p20_plan()
    p['p20_operation'] = 'rollback-services'
    p['previous_digests'] = {k: 'sha256:' + 'b' * 64 for k in release.SERVICES}
    release.validate_plan(p)
    del p['previous_digests']['keycloak']
    with pytest.raises(release.MigrationError, match='digests previos'):
        release.validate_plan(p)


def test_p20_activate_previous_plan_is_isolated_and_requires_prior_digests():
    p = p20_plan()
    p['p20_operation'] = 'activate-previous'
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    release.validate_plan(p)
    del p['previous_digests']['backend']
    with pytest.raises(release.MigrationError, match='digests previos'):
        release.validate_plan(p)


def test_p20_baseline_activation_only_changes_four_app_images_and_zero_to_one_capacity():
    before = rollback_template('bootstrap-placeholder', migration_tag='bootstrap-placeholder', count=0)
    after = rollback_template('previous', migration_tag='bootstrap-placeholder', count=1)
    release.assert_p20_baseline_activation_transition(before, after, 1)

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['migration']['Properties']['ContainerDefinitions'][0]['Image'] = 'repo:other'
    with pytest.raises(release.MigrationError, match='migración'):
        release.assert_p20_baseline_activation_transition(before, unsafe, 1)

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['db']['Properties']['BackupRetentionPeriod'] = 1
    with pytest.raises(release.MigrationError, match='recurso no permitido'):
        release.assert_p20_baseline_activation_transition(before, unsafe, 1)


def test_p20_previous_release_can_be_prepared_on_a_restored_database_without_migration():
    before = rollback_template('bootstrap-placeholder', migration_tag='bootstrap-placeholder', count=0)
    after = rollback_template('previous', migration_tag='bootstrap-placeholder', count=1)
    for target in (before, after):
        target['Resources']['formulario-publico']['Properties']['ContainerDefinitions'][0]['Name'] = 'frontend'
        target['Resources']['portal-interno']['Properties']['ContainerDefinitions'][0]['Name'] = 'portal'
    before['Outputs']['EcsDatabaseHost'] = {'Value': 'primary.p20.internal'}
    after['Outputs']['EcsDatabaseHost'] = {'Value': 'restore.p20.internal'}
    for name in ('backend', 'migration'):
        old = before['Resources'][name]['Properties']['ContainerDefinitions'][0]
        new = after['Resources'][name]['Properties']['ContainerDefinitions'][0]
        old['Environment'].append({'Name': 'DATABASE_HOST', 'Value': 'primary.p20.internal'})
        new['Environment'].append({'Name': 'DATABASE_HOST', 'Value': 'restore.p20.internal'})
    for name, host in [('keycloak', 'primary.p20.internal')]:
        before['Resources'][name]['Properties']['ContainerDefinitions'][0]['Environment'].append(
            {'Name': 'KC_DB_URL', 'Value': f'jdbc:postgresql://{host}:5432/sagrilaft'})
        after['Resources'][name]['Properties']['ContainerDefinitions'][0]['Environment'].append(
            {'Name': 'KC_DB_URL', 'Value': 'jdbc:postgresql://restore.p20.internal:5432/sagrilaft'})

    release.assert_p20_baseline_restored_db_transition(
        before, after, 1, 'restore.p20.internal', 'previous',
        'bootstrap-placeholder', 'p20-012345abcdef')

    # Si frontend y portal ya apuntan al baseline, sus task definitions no
    # necesitan una revisión nueva para activar los cuatro servicios.
    unchanged_optional_tasks = copy.deepcopy(before)
    for name in ('formulario-publico', 'portal-interno'):
        unchanged_optional_tasks['Resources'][name] = copy.deepcopy(after['Resources'][name])
    release.assert_p20_baseline_restored_db_transition(
        unchanged_optional_tasks, after, 1, 'restore.p20.internal', 'previous',
        'bootstrap-placeholder', 'p20-012345abcdef')

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['db']['Properties']['BackupRetentionPeriod'] = 1
    with pytest.raises(release.MigrationError, match='recurso ajeno'):
        release.assert_p20_baseline_restored_db_transition(
            before, unsafe, 1, 'restore.p20.internal', 'previous',
            'bootstrap-placeholder', 'p20-012345abcdef')

def test_p20_baseline_activation_allows_only_the_ten_approved_ascii_text_diffs():
    before = rollback_template('bootstrap-placeholder', migration_tag='bootstrap-placeholder', count=0)
    after = rollback_template('previous', migration_tag='bootstrap-placeholder', count=1)
    for path, expected, observed in release.P20_ASCII_PAIRS:
        set_template_path(before, path, observed)
        set_template_path(after, path, expected)
        if path[0] == 'Resources':
            before['Resources'][path[1]].setdefault('Type', 'AWS::CloudFormation::WaitCondition')
            after['Resources'][path[1]].setdefault('Type', 'AWS::CloudFormation::WaitCondition')
    release.assert_p20_baseline_activation_transition(before, after, 1, environment='p20-9c67b6ea6842')

    unsafe = copy.deepcopy(after)
    unsafe['Resources']['db']['Properties']['BackupRetentionPeriod'] = 1
    with pytest.raises(release.MigrationError):
        release.assert_p20_baseline_activation_transition(before, unsafe, 1, environment='p20-9c67b6ea6842')


def test_p20_baseline_activation_rejects_already_running_service():
    class Runtime:
        def aws(self, service, operation, *args):
            return {'services': [{'status': 'ACTIVE', 'desiredCount': 0,
                                  'runningCount': 1, 'pendingCount': 0,
                                  'deployments': [{'rolloutState': 'COMPLETED'}]}] * 4,
                    'failures': []}

    outputs = {'EcsClusterName': 'sagrilaft-p20-012345abcdef'}
    outputs.update({value: value for value in release.SERVICES.values()})
    with pytest.raises(release.MigrationError, match='detenidos'):
        release.require_p20_services_stopped(Runtime(), outputs)


def test_p20_previous_activation_preflight_is_read_only_and_never_migrates(tmp_path):
    p = p20_plan()
    p['p20_operation'] = 'activate-previous'
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    environment = p['environment']
    cluster = f'sagrilaft-{environment}'
    resources = {}
    outputs = {'EcsDesiredCount': {'Value': '0'}, 'EcsMigrationImageTag': {'Value': 'bootstrap'},
               'S3Bucket': {'Value': 'p20-evidence'}, 'EcsClusterName': {'Value': cluster}}
    service_names = {}
    repository_uris = {}
    for name in release.SERVICES:
        task_id, service_id = name + 'Task', name + 'Service'
        repo = f'{p["account"]}.dkr.ecr.us-east-1.amazonaws.com/sagrilaft-{environment}-{name}'
        resources[task_id] = {'Type': 'AWS::ECS::TaskDefinition', 'Properties': {
            'ContainerDefinitions': [{'Name': name, 'Image': repo + ':bootstrap',
                                      'Environment': [{'Name': 'GIT_SHA', 'Value': 'bootstrap'}]}]}}
        resources[service_id] = {'Type': 'AWS::ECS::Service', 'Properties': {
            'DesiredCount': 0, 'TaskDefinition': {'Ref': task_id}}}
        service_names[name] = f'{cluster}-{name}'
        repository_uris[name] = repo
    outputs.update({key: {'Value': service_names[name]} for name, key in release.SERVICES.items()})
    outputs.update({key: {'Value': repository_uris[name]} for name, key in release.REPOS.items()})
    resources['MigrationTask'] = {'Type': 'AWS::ECS::TaskDefinition', 'Properties': {
        'ContainerDefinitions': [{'Name': 'migration', 'Image': 'migration:bootstrap'}]}}
    baseline = {'Resources': resources, 'Outputs': outputs}

    class Runtime:
        def __init__(self):
            self.plan, self.directory = p, tmp_path
            self.stack = f'SagrilaftStack-{environment}'
            self.events, self.saved, self.deployments, self.migration_calls = [], {}, [], 0

        def aws(self, service, operation, *args):
            if (service, operation) == ('sts', 'get-caller-identity'):
                return {'Account': p['account']}
            if (service, operation) == ('cloudformation', 'describe-stacks'):
                return {'Stacks': [{'StackStatus': 'CREATE_COMPLETE', 'StackId':
                    f'arn:aws:cloudformation:us-east-1:{p["account"]}:stack/{self.stack}/id',
                    'Outputs': [{'OutputKey': key, 'OutputValue': value['Value']}
                                for key, value in outputs.items()]}]}
            if (service, operation) == ('cloudformation', 'get-template'):
                return {'TemplateBody': baseline}
            if (service, operation) == ('ecs', 'describe-services'):
                return {'failures': [], 'services': [{
                    'serviceName': service_names[name], 'status': 'ACTIVE', 'desiredCount': 0,
                    'runningCount': 0, 'pendingCount': 0,
                    'deployments': [{'rolloutState': 'COMPLETED'}]} for name in release.SERVICES]}
            if (service, operation) == ('ecr', 'describe-repositories'):
                return {'repositories': [{'imageTagMutability': 'IMMUTABLE'}]}
            if (service, operation) == ('ecr', 'describe-images'):
                kind = next(name for name, repo in service_names.items()
                            if f'sagrilaft-{environment}-{name}' in args[1])
                return {'imageDetails': [{'imageDigest': p['previous_digests'][kind]}]}
            pytest.fail(f'Unexpected AWS call: {service}/{operation}')

        def save(self, name, value): self.saved[name] = value
        def event(self, value): self.events.append(value)
        def synth(self, phase, image_tag, migration_tag, count):
            result = copy.deepcopy(baseline)
            for name in release.SERVICES:
                result['Resources'][name + 'Task']['Properties']['ContainerDefinitions'][0]['Image'] = f'{repository_uris[name]}:{image_tag}'
                result['Resources'][name + 'Task']['Properties']['ContainerDefinitions'][0]['Environment'][0]['Value'] = image_tag
                result['Resources'][name + 'Service']['Properties']['DesiredCount'] = count
            result['Outputs']['EcsDesiredCount']['Value'] = str(count)
            return result

        def deploy(self, phase): self.deployments.append(phase)

    runtime = Runtime()
    release.coordinate(runtime)
    assert not runtime.deployments and runtime.migration_calls == 0
    assert runtime.events[-1]['event'] == 'p20_previous_activation_preflight_validated'
    assert runtime.events[-1]['migrationWillRun'] is False


def test_p20_restored_database_connection_plan_is_run_scoped():
    p = p20_plan()
    p['p20_operation'] = 'connect-restored-db'
    p['context']['databaseHostOverride'] = 'restore-db.p20.internal'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-c7-test-20261012'
    release.validate_plan(p)

    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-c7-test-latest'
    with pytest.raises(release.MigrationError):
        release.validate_plan(p)

    p['environment'] = 'prod'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-restore-c'
    with pytest.raises(release.MigrationError):
        release.validate_plan(p)


def test_p20_activate_previous_restored_db_requires_scoped_database_and_previous_digests():
    p = p20_plan()
    p['p20_operation'] = 'activate-previous-restored-db'
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    p['context']['databaseHostOverride'] = 'restore-db.p20.internal'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-restore-c'
    release.validate_plan(p)

    del p['context']['databaseHostOverride']
    with pytest.raises(release.MigrationError, match='host de RDS restaurada'):
        release.validate_plan(p)


@pytest.mark.parametrize(('field', 'value'), [
    ('PubliclyAccessible', True), ('StorageEncrypted', False),
    ('DBInstanceClass', 'db.t3.micro'), ('MultiAZ', True), ('Engine', 'mysql'),
    ('EngineVersion', '15.7'),
])
def test_p20_restored_database_rejects_nonisolated_or_unapproved_profile(field, value):
    p = p20_plan()
    p['p20_operation'] = 'activate-previous-restored-db'
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    p['context']['databaseHostOverride'] = 'restore-db.p20.internal'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-restore-c'
    instance = {
        'DBInstanceIdentifier': 'p20-012345abcdef-restore-c',
        'DBInstanceStatus': 'available',
        'Endpoint': {'Address': 'restore-db.p20.internal'},
        'Engine': 'postgres', 'EngineVersion': '16.13', 'DBInstanceClass': 'db.t3.medium',
        'MultiAZ': False, 'PubliclyAccessible': False, 'StorageEncrypted': True,
        'DBSubnetGroup': {'VpcId': 'vpc-p20'},
        'VpcSecurityGroups': [{'VpcSecurityGroupId': 'sg-p20-rds'}],
        'DBInstanceArn': 'arn:aws:rds:us-east-1:123456789012:db/p20-restore',
    }
    instance[field] = value

    class ReadOnlyRuntime:
        plan = p

        def aws(self, service, operation, *args):
            if (service, operation) == ('rds', 'describe-db-instances'):
                return {'DBInstances': [instance]}
            if (service, operation) == ('rds', 'list-tags-for-resource'):
                return {'TagList': [
                    {'Key': 'Project', 'Value': 'sagrilaft'},
                    {'Key': 'Environment', 'Value': p['environment']},
                ]}
            pytest.fail(f'Unexpected AWS call: {service}/{operation}')

    outputs = {'P20VpcId': 'vpc-p20', 'P20RdsSecurityGroupId': 'sg-p20-rds'}
    with pytest.raises(release.MigrationError):
        release.verify_restored_database(ReadOnlyRuntime(), outputs)


def test_p20_restored_database_accepts_only_private_encrypted_p16_instance():
    p = p20_plan()
    p['context']['databaseHostOverride'] = 'restore-db.p20.internal'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-restore-c'
    instance = {
        'DBInstanceIdentifier': 'p20-012345abcdef-restore-c', 'DBInstanceStatus': 'available',
        'Endpoint': {'Address': 'restore-db.p20.internal'}, 'Engine': 'postgres',
        'EngineVersion': '16.13', 'DBInstanceClass': 'db.t3.medium', 'MultiAZ': False,
        'PubliclyAccessible': False, 'StorageEncrypted': True,
        'DBSubnetGroup': {'VpcId': 'vpc-p20'},
        'VpcSecurityGroups': [{'VpcSecurityGroupId': 'sg-p20-rds'}],
        'DBInstanceArn': 'arn:aws:rds:us-east-1:123456789012:db/p20-restore',
    }

    class ReadOnlyRuntime:
        plan = p

        def aws(self, service, operation, *args):
            if (service, operation) == ('rds', 'describe-db-instances'):
                return {'DBInstances': [instance]}
            if (service, operation) == ('rds', 'list-tags-for-resource'):
                return {'TagList': [
                    {'Key': 'Project', 'Value': 'sagrilaft'},
                    {'Key': 'Environment', 'Value': p['environment']},
                ]}
            pytest.fail(f'Unexpected AWS call: {service}/{operation}')

    outputs = {'P20VpcId': 'vpc-p20', 'P20RdsSecurityGroupId': 'sg-p20-rds'}
    result = release.verify_restored_database(ReadOnlyRuntime(), outputs)
    assert result['status'] == 'available' and result['host'] == 'restore-db.p20.internal'


def test_p20_restored_baseline_preflight_is_read_only_and_never_migrates(tmp_path, monkeypatch):
    p = p20_plan()
    p['p20_operation'] = 'activate-previous-restored-db'
    p['preflightOnly'] = True
    p['executionAuthorized'] = False
    p['previous_digests'] = {key: 'sha256:' + 'b' * 64 for key in release.SERVICES}
    p['context']['databaseHostOverride'] = 'restore-db.p20.internal'
    p['context']['restoredDbIdentifier'] = 'p20-012345abcdef-restore-c'
    outputs = {
        'EcsDesiredCount': '0', 'EcsMigrationImageTag': p['candidate_tag'],
        'EcsClusterName': 'sagrilaft-p20-012345abcdef', 'S3Bucket': 'p20-bucket',
    }

    class Runtime:
        def __init__(self):
            self.plan, self.directory = p, tmp_path
            self.stack, self.calls, self.deployments, self.events, self.saved = 'SagrilaftStack-' + p['environment'], [], [], [], {}

        def aws(self, service, operation, *args):
            self.calls.append((service, operation, args))
            if (service, operation) == ('sts', 'get-caller-identity'):
                return {'Account': p['account']}
            pytest.fail(f'Unexpected AWS call: {service}/{operation}')

        def save(self, name, value): self.saved[name] = copy.deepcopy(value)
        def event(self, value): self.events.append(copy.deepcopy(value))
        def synth(self, phase, image_tag, migration_tag, count):
            assert phase == 'activate-previous-restored-db'
            assert image_tag == p['previous_tag'] and migration_tag == p['candidate_tag'] and count == 1
            return {'Resources': {}, 'Outputs': {'EcsDesiredCount': {'Value': '1'},
                                                  'EcsDatabaseHost': {'Value': 'restore-db.p20.internal'}}}
        def deploy(self, phase): self.deployments.append(phase)

    checks = []
    monkeypatch.setattr(release, 'stack_state', lambda _rt: outputs)
    monkeypatch.setattr(release, 'require_p20_services_stopped', lambda *_args: checks.append('services_stopped'))
    monkeypatch.setattr(release, 'verify_restored_database', lambda *_args: {
        'identifier': 'p20-012345abcdef-restore-c', 'host': 'restore-db.p20.internal', 'status': 'available'})
    monkeypatch.setattr(release, 'verify_tag_digests', lambda *_args: checks.append('previous_digests'))
    monkeypatch.setattr(release, 'deployed_template', lambda _rt: {'Resources': {}, 'Outputs': {}})
    monkeypatch.setattr(release, 'assert_p20_baseline_restored_db_transition',
                        lambda *args: checks.append(('transition', args[2], args[3], args[4], args[5])))

    runtime = Runtime()
    release.coordinate(runtime)
    assert runtime.deployments == []
    assert runtime.saved['p20-restored-db-preflight.json']['status'] == 'available'
    assert runtime.events[-1]['event'] == 'p20_previous_restored_db_preflight_validated'
    assert runtime.events[-1]['migrationWillRun'] is False
    assert checks == ['services_stopped', 'previous_digests',
                      ('transition', 1, 'restore-db.p20.internal', p['previous_tag'], p['candidate_tag'])]
    assert all(operation not in {'put-object', 'delete-object', 'run-task', 'update-service'}
               for _, operation, _ in runtime.calls)

    with pytest.raises(release.MigrationError, match='solo preflight o no autoriza'):
        release.coordinate(runtime, execute=True)
    assert runtime.deployments == []
    assert all(operation not in {'put-object', 'delete-object', 'run-task', 'update-service'}
               for _, operation, _ in runtime.calls)


def test_database_repoint_transition_only_changes_database_endpoints():
    before = template('active', 'active', 0)
    before['Resources'].pop('service')
    for name in release.SERVICES:
        before['Resources'][name + 'Service'] = {
            'Type': 'AWS::ECS::Service', 'Properties': {'DesiredCount': 0, 'TaskDefinition': {'Ref': name}},
        }
    before['Outputs']['EcsDatabaseHost'] = {'Value': 'primary.p20.internal'}
    for name, host_key in [('backend', 'DATABASE_HOST'), ('migration', 'DATABASE_HOST'), ('keycloak', 'KC_DB_URL')]:
        container = before['Resources'][name]['Properties']['ContainerDefinitions'][0]
        container['Environment'].append({'Name': host_key, 'Value': 'primary.p20.internal' if host_key == 'DATABASE_HOST' else 'jdbc:postgresql://primary.p20.internal:5432/sagrilaft'})
    after = copy.deepcopy(before)
    after['Outputs']['EcsDatabaseHost'] = {'Value': 'restore-db.p20.internal'}
    for name, host_key in [('backend', 'DATABASE_HOST'), ('migration', 'DATABASE_HOST'), ('keycloak', 'KC_DB_URL')]:
        container = after['Resources'][name]['Properties']['ContainerDefinitions'][0]
        item = next(item for item in container['Environment'] if item['Name'] == host_key)
        item['Value'] = 'restore-db.p20.internal' if host_key == 'DATABASE_HOST' else 'jdbc:postgresql://restore-db.p20.internal:5432/sagrilaft'
    for name in release.SERVICES:
        after['Resources'][name + 'Service']['Properties']['DesiredCount'] = 1
    after['Outputs']['EcsDesiredCount'] = {'Value': '1'}
    after['Outputs']['EcsDatabaseHost'] = {'Value': 'restore-db.p20.internal'}
    release.assert_database_repoint_transition(before, after, 'restore-db.p20.internal', 1)

    after['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Image'] = 'repo:unexpected'
    with pytest.raises(release.MigrationError, match='imágenes'):
        release.assert_database_repoint_transition(before, after, 'restore-db.p20.internal', 1)


def rollback_template(service_tag, migration_tag='candidate', count=1):
    result = template(service_tag, migration_tag, count)
    result['Resources'].pop('service')
    for name in release.SERVICES:
        result['Resources'][name + 'Service'] = {
            'Type': 'AWS::ECS::Service',
            'Properties': {'DesiredCount': count, 'TaskDefinition': {'Ref': name}},
        }
    return result


def test_service_rollback_transition_only_changes_four_app_releases():
    before = rollback_template('candidate')
    after = rollback_template('previous')
    release.assert_service_rollback_transition(before, after)

    migration_change = copy.deepcopy(after)
    migration_change['Resources']['migration']['Properties']['ContainerDefinitions'][0]['Image'] = 'repo:other'
    with pytest.raises(release.MigrationError, match='migración'):
        release.assert_service_rollback_transition(before, migration_change)

    db_change = copy.deepcopy(after)
    db_change['Resources']['db']['Properties']['BackupRetentionPeriod'] = 1
    with pytest.raises(release.MigrationError, match='recurso no permitido'):
        release.assert_service_rollback_transition(before, db_change)


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


def manual_runtime(runtime):
    runtime.plan.update(smoke_mode="manual", smoke_command=[], manual_checks=list(release.MANUAL_CHECKS))
    original = runtime.save
    def save(name, value):
        original(name, value)
        (runtime.directory / name).write_text(json.dumps(value))
    runtime.save = save
    return runtime


def approve_manual(rt):
    record = release.read_json(rt.directory / 'manual-validation.json')
    (rt.directory / 'capture.txt').write_text('Redacted functional evidence for this test')
    record.update(status='approved', operator='Reviewer', completedAt=release.utc_now(),
                  formularioId='form-test', accesoId='access-test')
    for check in record['checks'].values():
        check.update(status='passed', evidence=['capture.txt'])
    rt.save('manual-validation.json', record)
    return record


def test_manual_preflight_does_not_create_pending_or_mutate(runtime):
    rt = manual_runtime(runtime)
    release.coordinate(rt)
    assert not rt.locked and not rt.deployments and not rt.migration_calls
    assert 'manual-state.json' not in rt.saved


def test_manual_activation_keeps_lock_and_returns_pending(runtime):
    rt = manual_runtime(runtime)
    assert release.coordinate(rt, True) == 3
    assert rt.locked and not rt.smoked and rt.migration_calls == 1
    assert rt.saved['manual-validation.json']['status'] == 'pending'
    assert not any(e['event'] == 'release_completed' for e in rt.events)


def test_manual_local_review_then_close_without_redeploy(runtime):
    rt = manual_runtime(runtime)
    release.coordinate(rt, True)
    approve_manual(rt)
    rt.calls.clear()
    assert release.close_manual(rt) == 0
    assert rt.calls == [] and rt.locked
    assert release.close_manual(rt, True) == 0
    assert not rt.locked and rt.migration_calls == 1
    assert rt.deployments == ['prepare', 'activate']
    assert rt.events[-1]['event'] == 'release_completed'
    assert rt.saved['manual-state.json']['status'] == 'completed'
    with pytest.raises(release.MigrationError):
        release.close_manual(rt, True)


@pytest.mark.parametrize('problem', ['pending', 'failed', 'sha', 'run', 'plan', 'operator', 'ids',
                                    'checks', 'check_failed', 'missing_file', 'empty_file', 'outside',
                                    'date', 'schema', 'retention'])
def test_manual_bad_evidence_keeps_lock_without_aws(runtime, problem):
    rt = manual_runtime(runtime)
    release.coordinate(rt, True)
    record = approve_manual(rt)
    if problem in ('pending', 'failed'): record['status'] = problem
    if problem == 'sha': record['candidate'] = 'b' * 40
    if problem == 'run': record['runId'] = 'other'
    if problem == 'plan': record['planHash'] = 'other'
    if problem == 'operator': record['operator'] = ''
    if problem == 'ids': record['formularioId'] = ''
    if problem == 'checks': del record['checks']['release_sha']
    if problem == 'check_failed': record['checks']['release_sha']['status'] = 'failed'
    if problem == 'missing_file': (rt.directory / 'capture.txt').unlink()
    if problem == 'empty_file': (rt.directory / 'capture.txt').write_text('')
    if problem == 'outside': record['checks']['release_sha']['evidence'] = ['../outside']
    if problem == 'date': record['completedAt'] = '2000-01-01T00:00:00+00:00'
    if problem == 'schema': rt.save('schema-evidence.json', {})
    if problem == 'retention': record['retention'] = 'deleted'
    rt.save('manual-validation.json', record)
    rt.calls.clear()
    with pytest.raises(release.MigrationError):
        release.close_manual(rt, True)
    assert rt.locked and rt.calls == []


@pytest.mark.parametrize('problem', ['lock', 'template', 'images', 'account', 'delete'])
def test_manual_close_rechecks_runtime_and_keeps_failure_uncompleted(runtime, problem):
    rt = manual_runtime(runtime)
    release.coordinate(rt, True)
    approve_manual(rt)
    if problem == 'lock': rt.lock_lost = True
    if problem == 'template': rt.current['Resources']['db']['Properties']['BackupRetentionPeriod'] = 1
    if problem == 'images':
        original = rt.aws
        def aws(service, operation, *args):
            result = original(service, operation, *args)
            if operation == 'describe-tasks':
                result['tasks'][0]['containers'][0]['imageDigest'] = 'sha256:' + 'b' * 64
            return result
        rt.aws = aws
    if problem == 'account': rt.account = '999999999999'
    if problem == 'delete': rt.fail = 'delete-object'
    with pytest.raises(release.MigrationError):
        release.close_manual(rt, True)
    assert rt.locked and rt.saved['manual-state.json']['status'] == 'pending_manual'
    assert not any(e['event'] == 'release_completed' for e in rt.events)


@pytest.mark.parametrize('problem', ['prod', 'command', 'checks', 'mode'])
def test_manual_plan_rejects_ambiguous_configuration(problem):
    p = plan()
    p.update(smoke_mode='manual', smoke_command=[], manual_checks=list(release.MANUAL_CHECKS))
    if problem == 'prod': p['environment'] = 'prod'
    if problem == 'command': p['smoke_command'] = ['true']
    if problem == 'checks': p['manual_checks'] = []
    if problem == 'mode': p['smoke_mode'] = 'skip'
    with pytest.raises(release.MigrationError): release.validate_plan(p)



def test_manual_changed_evidence_during_close_is_rejected(runtime):
    rt = manual_runtime(runtime)
    release.coordinate(rt, True)
    approve_manual(rt)
    original = rt.aws
    def aws(service, operation, *args):
        if operation == 'describe-services':
            (rt.directory / 'capture.txt').write_text('Changed while checking ECS')
        return original(service, operation, *args)
    rt.aws = aws
    with pytest.raises(release.MigrationError, match='Evidencia cambió'):
        release.close_manual(rt, True)
    assert rt.locked and all(op != 'delete-object' for _, op, _ in rt.calls)


def test_cli_pending_returns_three_without_calling_real_runtime(tmp_path, monkeypatch):
    p = plan()
    p.update(smoke_mode='manual', smoke_command=[], manual_checks=list(release.MANUAL_CHECKS))
    plan_path = tmp_path / 'input.json'
    plan_path.write_text(json.dumps(p))
    monkeypatch.setattr(sys, 'argv', ['deploy_release', '--plan', str(plan_path),
                                    '--environment', 'staging', '--evidence-dir', str(tmp_path / 'run'), '--execute'])
    def coordinate(rt, execute):
        assert execute and rt.plan == p
        return 3
    monkeypatch.setattr(release, 'coordinate', coordinate)
    monkeypatch.setattr(release.Runtime, 'aws', lambda *a: pytest.fail('No real AWS permitted'))
    assert release.main() == 3


def test_atomic_save_replaces_complete_json_with_private_permissions(tmp_path):
    rt = release.Runtime(plan(), tmp_path)
    rt.save('state.json', {'status': 'pending'})
    rt.save('state.json', {'status': 'completed', 'texto': 'validación'})
    assert release.read_json(tmp_path / 'state.json')['status'] == 'completed'
    assert (tmp_path / 'state.json').stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == ['state.json']


@pytest.mark.parametrize('stage', ['serialize', 'write', 'file_fsync', 'replace'])
def test_atomic_failure_preserves_previous_evidence(tmp_path, monkeypatch, stage):
    rt = release.Runtime(plan(), tmp_path)
    rt.save('state.json', {'status': 'pending'})
    before = (tmp_path / 'state.json').read_bytes()
    def fail(*args, **kwargs): raise OSError('simulated disk error')
    if stage == 'write': monkeypatch.setattr(release.os, 'fchmod', fail)
    if stage == 'file_fsync': monkeypatch.setattr(release.os, 'fsync', fail)
    if stage == 'replace': monkeypatch.setattr(release.os, 'replace', fail)
    value = {'bad': object()} if stage == 'serialize' else {'status': 'completed'}
    with pytest.raises((OSError, TypeError)):
        rt.save('state.json', value)
    assert (tmp_path / 'state.json').read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ['state.json']


def test_directory_fsync_failure_reports_error_but_json_remains_complete(tmp_path, monkeypatch):
    rt = release.Runtime(plan(), tmp_path)
    rt.save('state.json', {'status': 'pending'})
    original = release.os.fsync
    calls = []
    def fsync(fd):
        calls.append(fd)
        if len(calls) == 2: raise OSError('directory sync failed')
        return original(fd)
    monkeypatch.setattr(release.os, 'fsync', fsync)
    with pytest.raises(OSError): rt.save('state.json', {'status': 'completed'})
    assert release.read_json(tmp_path / 'state.json') == {'status': 'completed'}


def test_events_atomic_failure_preserves_existing_history(tmp_path, monkeypatch):
    rt = release.Runtime(plan(), tmp_path)
    rt.event({'event': 'first'})
    def fail(*args): raise OSError('replace failed')
    monkeypatch.setattr(release.os, 'replace', fail)
    with pytest.raises(OSError): rt.event({'event': 'second'})
    assert (tmp_path / 'events.jsonl').read_text().splitlines() == ['{"event": "first"}']


@pytest.mark.parametrize('dirty', [False, True])
def test_orchestrator_records_commit_and_exact_sources(tmp_path, monkeypatch, dirty):
    root = tmp_path / 'checkout'
    (root / 'scripts').mkdir(parents=True)
    for name in release.ORCHESTRATOR_SOURCES:
        (root / name).write_text('source with unicode: validación\n')
    directory = tmp_path / 'evidence'
    directory.mkdir()
    def git(args, **kwargs):
        assert args[0] == 'git'
        return 'b' * 40 if args[1] == 'rev-parse' else (' M scripts/deploy_release.py' if dirty else '')
    monkeypatch.setattr(release.subprocess, 'check_output', git)
    rt = release.Runtime(plan(), directory)
    release.record_orchestrator(rt, root=root)
    data = release.read_json(directory / 'orchestrator.json')
    assert data['baseCommit'] == 'b' * 40
    assert data['orchestratorModified'] is dirty and data['checkoutDirty'] is dirty
    assert data['candidateTag'] == plan()['candidate_tag']
    for name, digest in data['sourceSha256'].items():
        content = (directory / data['snapshotDirectory'] / Path(name).name).read_bytes()
        assert content == (root / name).read_bytes()
        assert release.hashlib.sha256(content).hexdigest() == digest


def unicode_template(path, value):
    result = value
    for key in reversed(path):
        if isinstance(key, int):
            parent = [None] * (key + 1)
            parent[key] = result
            result = parent
        else:
            result = {key: result}
    return result


def set_template_path(root, path, value):
    cursor = root
    for index, key in enumerate(path[:-1]):
        following = path[index + 1]
        if isinstance(cursor, list):
            while len(cursor) <= key:
                cursor.append(None)
            if cursor[key] is None:
                cursor[key] = [] if isinstance(following, int) else {}
            cursor = cursor[key]
        else:
            if key not in cursor:
                cursor[key] = [] if isinstance(following, int) else {}
            cursor = cursor[key]
    if isinstance(cursor, list):
        while len(cursor) <= path[-1]:
            cursor.append(None)
    cursor[path[-1]] = value


@pytest.mark.parametrize('path,original,observed', release.STAGING_UNICODE_PAIRS)
def test_only_exact_approved_unicode_pair_is_equivalent(path, original, observed):
    expected = unicode_template(path, original)
    actual = unicode_template(path, observed)
    snapshot = copy.deepcopy(actual)
    assert release.comparison_template(actual, 'staging') == release.comparison_template(expected, 'staging')
    assert actual == snapshot  # Nunca alterar el artefacto recibido.
    assert release.comparison_template(actual, 'prod') != release.comparison_template(expected, 'prod')
    changed = unicode_template(path, observed + ' CAMBIO')
    assert release.comparison_template(changed, 'staging') != release.comparison_template(expected, 'staging')
    other_path = ('OtherResource', *path[1:])
    assert release.comparison_template(unicode_template(other_path, observed), 'staging') != release.comparison_template(unicode_template(other_path, original), 'staging')


@pytest.mark.parametrize('path,expected,observed', release.P20_ASCII_PAIRS)
def test_p20_only_exact_observed_text_maps_to_approved_ascii(path, expected, observed):
    before = unicode_template(path, observed)
    after = unicode_template(path, expected)
    snapshot = copy.deepcopy(before)
    assert release.comparison_template(before, 'p20-9c67b6ea6842') == release.comparison_template(after, 'p20-9c67b6ea6842')
    assert before == snapshot
    assert release.comparison_template(before, 'staging') != release.comparison_template(after, 'staging')
    assert release.comparison_template(before, 'prod') != release.comparison_template(after, 'prod')
    changed = unicode_template(path, observed + ' extra')
    assert release.comparison_template(changed, 'p20-9c67b6ea6842') != release.comparison_template(after, 'p20-9c67b6ea6842')


def test_p20_ascii_equivalences_do_not_allow_other_resource_changes():
    before = template()
    after = template()
    for path, expected, observed in release.P20_ASCII_PAIRS:
        for target, value in ((before, observed), (after, expected)):
            set_template_path(target, path, value)
    assert release.comparison_template(before, 'p20-9c67b6ea6842') == release.comparison_template(after, 'p20-9c67b6ea6842')
    after['Outputs']['extra'] = {'Value': 'unapproved'}
    assert release.comparison_template(before, 'p20-9c67b6ea6842') != release.comparison_template(after, 'p20-9c67b6ea6842')


def test_unicode_exception_does_not_hide_retention_or_image_changes():
    path, original, observed = release.STAGING_UNICODE_PAIRS[0]
    expected = unicode_template(path, original)
    actual = unicode_template(path, observed.replace('30', '31'))
    assert release.comparison_template(actual, 'staging') != release.comparison_template(expected, 'staging')
    before = template()
    after = template(migration_tag='new')
    before['Resources'].update(unicode_template(path, original)['Resources'])
    after['Resources'].update(unicode_template(path, observed)['Resources'])
    release.assert_transition(before, after, 'prepare', environment='staging')
    after['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Image'] = 'unauthorized'
    with pytest.raises(release.MigrationError):
        release.assert_transition(before, after, 'prepare', environment='staging')


@pytest.mark.parametrize('env', ['staging', 'prod', None])
def test_comparison_preserves_original_metadata_policy(env):
    value = template()
    value['Metadata'] = {'owner': 'example'}
    value['Resources']['db']['Metadata'] = {'revision': 1}
    value['Resources']['CDKMetadata'] = {'Type': 'AWS::CDK::Metadata', 'Properties': {'Analytics': 'example'}}
    snapshot = copy.deepcopy(value)
    assert release.comparison_template(value, env) == release.strip_metadata(value)
    assert release.comparison_template(value, env, preserve_metadata=True) == value
    assert value == snapshot


@pytest.mark.parametrize('kind', ['root', 'resource', 'telemetry'])
def test_metadata_change_after_lock_blocks_preparation(runtime, kind):
    original = runtime.aws
    reads = 0
    def aws(service, operation, *args):
        nonlocal reads
        response = original(service, operation, *args)
        if operation == 'get-template':
            reads += 1
            if reads == 2:
                body = response['TemplateBody']
                if kind == 'root': body['Metadata'] = {'changed': True}
                if kind == 'resource': body['Resources']['db']['Metadata'] = {'changed': True}
                if kind == 'telemetry': body['Resources']['CDKMetadata'] = {'Type': 'AWS::CDK::Metadata'}
        return response
    runtime.aws = aws
    with pytest.raises(release.MigrationError, match='Stack cambió'):
        release.coordinate(runtime, True)
    assert runtime.locked and runtime.deployments == [] and runtime.migration_calls == 0


@pytest.mark.parametrize('path,original,observed', release.STAGING_UNICODE_PAIRS)
def test_strict_baseline_accepts_only_approved_unicode_preserving_metadata(path, original, observed):
    a = unicode_template(path, original)
    b = unicode_template(path, observed)
    a['Metadata'] = b['Metadata'] = {'same': True}
    assert release.comparison_template(a, 'staging', preserve_metadata=True) == release.comparison_template(b, 'staging', preserve_metadata=True)
    b['Metadata'] = {'same': False}
    assert release.comparison_template(a, 'staging', preserve_metadata=True) != release.comparison_template(b, 'staging', preserve_metadata=True)


class BackendStartupLogsRuntime:
    """Simula únicamente las lecturas ECS/Logs del verificador de arranque."""
    def __init__(self):
        self.plan = {'account': '123456789012', 'region': 'us-east-1'}
        self.environment = 'p20-012345abcdef'
        self.outputs = {'EcsBackendServiceName': 'backend-service',
                        'EcsClusterName': 'sagrilaft-' + self.environment}
        self.task_arn = ('arn:aws:ecs:us-east-1:123456789012:task/'
                         + self.outputs['EcsClusterName'] + '/' + 'a' * 32)
        self.definition_arn = ('arn:aws:ecs:us-east-1:123456789012:task-definition/'
                               'sagrilaft-p20-012345abcdef-backend:5')
        self.services = [{'serviceName': 'backend-service', 'taskDefinition': self.definition_arn,
                          'verifiedTasks': [{'taskArn': self.task_arn}]}]
        self.task = {'taskArn': self.task_arn, 'taskDefinitionArn': self.definition_arn,
                     'lastStatus': 'RUNNING', 'containers': [{'name': 'backend'}]}
        self.group = '/sagrilaft/' + self.environment + '/ecs/backend'
        self.stream = 'custom-prefix/backend/' + 'a' * 32
        self.options = {'awslogs-group': self.group, 'awslogs-region': 'us-east-1',
                        'awslogs-stream-prefix': 'custom-prefix'}
        self.elapsed, self.available_at, self.marker_at = 0, 0, 0
        self.calls = []
        self.extra_stream_suffix = ''
        self.fail = None
        self.pages = []
        self.stop_at = None

    def sleep(self, seconds):
        self.elapsed += seconds

    def clock(self):
        return self.elapsed

    def aws(self, service, operation, *args):
        self.calls.append((service, operation, args))
        if operation == self.fail:
            raise release.MigrationError('AWS: acceso denegado o resultado incierto')
        if (service, operation) == ('ecs', 'describe-task-definition'):
            assert args == ('--task-definition', self.definition_arn)
            return {'taskDefinition': {'taskDefinitionArn': self.definition_arn,
                    'containerDefinitions': [{'name': 'backend', 'logConfiguration': {
                        'logDriver': 'awslogs', 'options': self.options}}]}}
        if (service, operation) == ('ecs', 'describe-tasks'):
            assert args == ('--cluster', self.outputs['EcsClusterName'], '--tasks', self.task_arn)
            if self.stop_at is not None and self.elapsed >= self.stop_at:
                self.task['lastStatus'] = 'STOPPED'
            return {'tasks': [self.task]}
        if (service, operation) == ('logs', 'describe-log-streams'):
            assert args == ('--log-group-name', self.group, '--log-stream-name-prefix', self.stream)
            return {'logStreams': [{'logStreamName': self.stream + self.extra_stream_suffix}]
                    if self.elapsed >= self.available_at else []}
        if (service, operation) == ('logs', 'filter-log-events'):
            assert args[args.index('--log-stream-names') + 1] == self.stream
            assert args[args.index('--log-group-name') + 1] == self.group
            assert '--no-paginate' in args
            if self.pages:
                return self.pages.pop(0)
            return {'events': [{'message': '[entrypoint] Base de datos disponible (intento 1).',
                                'logStreamName': self.stream}]
                    if self.elapsed >= self.marker_at else []}
        pytest.fail(f'Operación ajena a lectura ECS/Logs: {service}/{operation}')

    def verify(self):
        return release.verify_p20_backend_database_startup(
            self, self.outputs, self.services, self.environment,
            sleep=self.sleep, clock=self.clock)


def test_backend_startup_resolves_awslogs_without_ecs_log_stream_field():
    rt = BackendStartupLogsRuntime()
    result = rt.verify()
    assert result['taskArn'] == rt.task_arn and result['logStream'] == rt.stream
    assert rt.elapsed == 0


def test_backend_startup_waits_for_stream_and_then_marker():
    rt = BackendStartupLogsRuntime()
    rt.available_at, rt.marker_at = 4, 8
    assert rt.verify()['databaseConnectivity'].startswith('SELECT 1 succeeded')
    assert rt.elapsed == 8
    assert sum(op == 'filter-log-events' for _, op, _ in rt.calls) == 3


@pytest.mark.parametrize('missing', ['stream', 'marker', 'different-stream'])
def test_backend_startup_times_out_without_using_other_task_logs(missing):
    rt = BackendStartupLogsRuntime()
    if missing == 'stream': rt.available_at = 100
    if missing == 'marker': rt.marker_at = 100
    if missing == 'different-stream': rt.extra_stream_suffix = '-other-task'
    with pytest.raises(release.MigrationError, match='conservar evidencia y lock'):
        rt.verify()
    assert rt.elapsed == 60
    if missing != 'marker':
        assert not any(op == 'filter-log-events' for _, op, _ in rt.calls)


def test_backend_startup_follows_empty_log_page_without_losing_marker():
    rt = BackendStartupLogsRuntime()
    rt.pages = [{'events': [], 'nextToken': 'page-2'}]
    assert rt.verify()['logStream'] == rt.stream
    log_calls = [args for _, op, args in rt.calls if op == 'filter-log-events']
    assert log_calls[1][-2:] == ('--next-token', 'page-2')


@pytest.mark.parametrize('operation', ['describe-task-definition', 'describe-tasks',
                                       'describe-log-streams', 'filter-log-events'])
def test_backend_startup_does_not_retry_aws_errors_or_modify_resources(operation):
    rt = BackendStartupLogsRuntime()
    rt.fail = operation
    with pytest.raises(release.MigrationError, match='acceso denegado'):
        rt.verify()
    assert rt.elapsed == 0
    assert sum(op == operation for _, op, _ in rt.calls) == 1


@pytest.mark.parametrize('option,value', [('awslogs-group', '/sagrilaft/staging/ecs/backend'),
                                         ('awslogs-region', 'eu-west-1'),
                                         ('awslogs-stream-prefix', '')])
def test_backend_startup_rejects_wrong_log_configuration(option, value):
    rt = BackendStartupLogsRuntime()
    rt.options[option] = value
    with pytest.raises(release.MigrationError, match='Configuración awslogs'):
        rt.verify()
    assert not any(service == 'logs' for service, _, _ in rt.calls)


def test_backend_startup_stops_if_task_stops_while_waiting():
    rt = BackendStartupLogsRuntime()
    rt.available_at, rt.stop_at = 100, 2
    with pytest.raises(release.MigrationError, match='dejó de estar RUNNING'):
        rt.verify()
    assert rt.elapsed == 2


@pytest.mark.parametrize('field,value', [('taskArn', 'another-task'),
                                       ('taskDefinitionArn', 'another-definition')])
def test_backend_startup_rejects_changed_task_identity(field, value):
    rt = BackendStartupLogsRuntime()
    rt.task[field] = value
    with pytest.raises(release.MigrationError, match='La tarea backend cambió'):
        rt.verify()
    assert not any(service == 'logs' for service, _, _ in rt.calls)
