"""Scenario A coordinator: immutable baseline and one inert task, with simulated AWS."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import deploy_release as release
from test_deploy_release import p20_plan


def scenario_plan():
    p = p20_plan()
    p.update(p20_operation='scenario-a-fixture', p20_migration_fault='fail-before-ddl',
             backend_image_tag='b' * 40, backend_image_digest='sha256:' + 'b' * 64,
             previous_digests={k: 'sha256:' + 'c' * 64 for k in release.SERVICES},
             baseline_template_sha256=release.fingerprint({'Resources': {}}),
             recovery_snapshot_identifier=p['environment'] + '-c7-base-20261012',
             smoke_command=[], executionAuthorized=True)
    p['expected_head'] = 'c7a1c1a65662'
    p['previous_revisions'] = [p['expected_head']]
    p['context'].update(databaseHostOverride='clone.internal',
                        restoredDbIdentifier=p['environment'] + '-c7-test-20261012')
    prefix = f"arn:aws:ecs:{p['region']}:{p['account']}:task-definition/sagrilaft-{p['environment']}-"
    p['baseline_task_definitions'] = {k: prefix + {'formulario-publico': 'frontend', 'portal-interno': 'portal'}.get(k, k) + ':4'
                                      for k in [*release.SERVICES, 'migration']}
    return p


class FixtureRuntime:
    def __init__(self, directory, fault='fail-before-ddl'):
        self.directory = directory
        self.plan = scenario_plan()
        self.plan['p20_migration_fault'] = fault
        self.stack = 'SagrilaftStack-' + self.plan['environment']
        self.calls, self.events, self.saved = [], [], {}
        self.locked, self.lock_lost, self.fail_run, self.lock_busy = False, False, False, False
        self.exit_code = 42
        p = self.plan
        prefix = f"arn:aws:ecs:{p['region']}:{p['account']}:"
        self.outputs = {'EcsClusterName': 'sagrilaft-' + p['environment'], 'S3Bucket': 'p20-lock-bucket',
                        'EcsMigrationTaskDefinitionArn': p['baseline_task_definitions']['migration'],
                        'EcsSecurityGroupId': 'sg-abc123', 'EcrBackendUri':
                        f"{p['account']}.dkr.ecr.{p['region']}.amazonaws.com/sagrilaft-{p['environment']}-backend"}
        self.network = {'subnets': ['subnet-abc123'], 'securityGroups': ['sg-abc123'], 'assignPublicIp': 'DISABLED'}
        self.task = prefix + 'task/' + self.outputs['EcsClusterName'] + '/fixture123'

    def save(self, name, value): self.saved[name] = copy.deepcopy(value)
    def event(self, value): self.events.append(value)
    def synth(self, *args): pytest.fail('Scenario A must not synthesize')
    def deploy(self, *args): pytest.fail('Scenario A must not deploy')
    def smoke(self): pytest.fail('Scenario A must not smoke')

    def aws(self, service, operation, *args):
        self.calls.append((service, operation, args))
        p, out = self.plan, self.outputs
        if operation == 'list-objects-v2':
            return {'Contents': [{'Key': f'_deployment/{self.stack}.lock'}]} if self.lock_busy else {}
        if operation == 'put-object':
            assert args[args.index('--if-none-match') + 1] == '*'
            assert args[args.index('--expected-bucket-owner') + 1] == p['account']
            self.locked = True
            return {'ETag': 'owned'}
        if operation == 'head-object': return {'ETag': 'other' if self.lock_lost else 'owned'}
        if operation == 'get-caller-identity': return {'Account': p['account']}
        if operation == 'describe-clusters':
            return {'clusters': [{'clusterArn': f"arn:aws:ecs:{p['region']}:{p['account']}:cluster/{out['EcsClusterName']}", 'status': 'ACTIVE'}]}
        if operation == 'describe-task-definition':
            return {'taskDefinition': {'taskDefinitionArn': out['EcsMigrationTaskDefinitionArn'], 'status': 'ACTIVE',
                    'networkMode': 'awsvpc', 'requiresCompatibilities': ['FARGATE'], 'containerDefinitions': [{
                    'name': 'migration', 'image': out['EcrBackendUri'] + ':' + p['candidate_tag'],
                    'environment': [{'name': 'RUN_MODE', 'value': 'migrate'}, {'name': 'GIT_SHA', 'value': p['candidate_tag']}]}]}}
        if operation == 'describe-images': return {'imageDetails': [{'imageDigest': p['digests']['backend']}]}
        if operation == 'run-task':
            if self.fail_run: raise release.MigrationError('RunTask incierto')
            return {'tasks': [{'taskArn': self.task}]}
        if operation == 'describe-tasks':
            return {'tasks': [{'taskArn': self.task, 'clusterArn': f"arn:aws:ecs:{p['region']}:{p['account']}:cluster/{out['EcsClusterName']}",
                    'taskDefinitionArn': out['EcsMigrationTaskDefinitionArn'], 'lastStatus': 'STOPPED',
                    'containers': [{'name': 'migration', 'image': out['EcrBackendUri'] + ':' + p['candidate_tag'],
                                    'imageDigest': p['digests']['backend'], 'exitCode': self.exit_code}]}]}
        pytest.fail(f'Unexpected/mutating AWS operation {service}/{operation}')


@pytest.fixture
def fixture_runtime(tmp_path, monkeypatch):
    rt = FixtureRuntime(tmp_path)
    monkeypatch.setattr(release, 'p20_scenario_a_baseline', lambda runtime: (runtime.outputs, runtime.network))
    monkeypatch.setattr(release, 'verify_p20_fixture_image_config', lambda *args: {'entrypoint': None})
    return rt


@pytest.mark.parametrize('fault', ['fail-before-ddl', 'observer-loss-after-launch'])
def test_preflight_never_writes_launches_synthesizes_or_migrates(fixture_runtime, fault):
    rt = fixture_runtime
    rt.plan['p20_migration_fault'] = fault
    release.coordinate(rt)
    assert [op for _, op, _ in rt.calls] == ['list-objects-v2']
    assert rt.events[-1]['event'] == 'p20_scenario_a_preflight_validated'
    assert not rt.locked


@pytest.mark.parametrize('mutation', ['staging', 'prod', 'reference', 'other-run', 'missing-fault', 'smoke', 'template-hash', 'task-definition', 'capacity', 'snapshot'])
def test_plan_rejects_unsafe_targets_and_operations(mutation):
    p = scenario_plan()
    if mutation in ('staging', 'prod'): p['environment'] = mutation
    if mutation == 'reference': p['context']['restoredDbIdentifier'] = p['environment'] + '-restore-20261009c'
    if mutation == 'other-run': p['context']['restoredDbIdentifier'] = 'p20-ffffffffffff-c7-test-20261012'
    if mutation == 'missing-fault': del p['p20_migration_fault']
    if mutation == 'smoke': p['smoke_command'] = ['run-smoke']
    if mutation == 'template-hash': p['baseline_template_sha256'] = 'unknown'
    if mutation == 'task-definition': p['baseline_task_definitions']['migration'] = 'staging-migration:4'
    if mutation == 'capacity': p['desired_count'] = 2
    if mutation == 'snapshot': p['recovery_snapshot_identifier'] = 'staging-snapshot'
    with pytest.raises(release.MigrationError): release.validate_plan(p)


@pytest.mark.parametrize('field,value', [('preflightOnly', True), ('executionAuthorized', False)])
def test_preflight_plan_cannot_execute(fixture_runtime, field, value):
    rt = fixture_runtime
    rt.plan[field] = value
    with pytest.raises(release.MigrationError, match='autorización independiente'): release.coordinate(rt, True)
    assert rt.calls == []


@pytest.mark.parametrize('fault,exit_code', [('fail-before-ddl', 42), ('fail-before-ddl', 0), ('observer-loss-after-launch', 42)])
def test_real_launcher_keeps_lock_and_never_reports_migration_success(fixture_runtime, fault, exit_code):
    rt = fixture_runtime
    rt.plan['p20_migration_fault'], rt.exit_code = fault, exit_code
    with pytest.raises(release.MigrationError): release.coordinate(rt, True)
    assert rt.locked
    assert sum(op == 'run-task' for _, op, _ in rt.calls) == 1
    assert not any(op == 'delete-object' for _, op, _ in rt.calls)
    assert not any(e['event'] in ('migration_completed', 'release_completed') for e in rt.events)
    assert rt.events[-1]['event'] == 'p20_scenario_a_reconciliation_required'
    if fault == 'observer-loss-after-launch': assert not any(op == 'describe-tasks' for _, op, _ in rt.calls)
    request = next(e for e in rt.events if e['event'] == 'migration_request')
    run = next(args for _, op, args in rt.calls if op == 'run-task')
    token = run[run.index('--client-token') + 1]
    assert token not in json.dumps(rt.saved) + json.dumps(rt.events)
    assert request['clientTokenSha256'] == hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.parametrize('failure', ['busy', 'lost', 'uncertain', 'changed'])
def test_lock_race_and_uncertainty_never_retries_or_unlocks(fixture_runtime, monkeypatch, failure):
    rt = fixture_runtime
    rt.lock_busy, rt.lock_lost, rt.fail_run = failure == 'busy', failure == 'lost', failure == 'uncertain'
    if failure == 'changed':
        reads = []
        def baseline(runtime):
            reads.append(1)
            if len(reads) > 1: raise release.MigrationError('baseline changed')
            return runtime.outputs, runtime.network
        monkeypatch.setattr(release, 'p20_scenario_a_baseline', baseline)
    with pytest.raises(release.MigrationError): release.coordinate(rt, True)
    assert sum(op == 'run-task' for _, op, _ in rt.calls) == (1 if failure == 'uncertain' else 0)
    assert not any(op == 'delete-object' for _, op, _ in rt.calls)
    assert rt.locked == (failure != 'busy')


def test_no_fallback_to_general_coordinator_on_fixture_return(fixture_runtime, monkeypatch):
    monkeypatch.setattr(release, 'run_migration', lambda *args, **kwargs: None)
    with pytest.raises(release.MigrationError, match='retornó inesperadamente'): release.coordinate(fixture_runtime, True)
    assert fixture_runtime.locked


@pytest.mark.parametrize('mutation', ['entrypoint', 'directory', 'platform', 'digest', 'download-error'])
def test_image_config_rejects_unsafe_or_unverifiable_image(tmp_path, monkeypatch, mutation):
    rt = FixtureRuntime(tmp_path)
    config = {'config': {'WorkingDir': '/app', 'Entrypoint': None}, 'os': 'linux', 'architecture': 'amd64'}
    if mutation == 'entrypoint': config['config']['Entrypoint'] = ['sh', 'entrypoint.sh']
    if mutation == 'directory': config['config']['WorkingDir'] = '/elsewhere'
    if mutation == 'platform': config['architecture'] = 'arm64'
    raw = json.dumps(config).encode()
    digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
    manifest = json.dumps({'config': {'digest': digest}})
    rt.plan['digests']['backend'] = 'sha256:' + hashlib.sha256(manifest.encode()).hexdigest()
    def aws(service, operation, *args):
        if operation == 'batch-get-image': return {'images': [{'imageManifest': manifest}]}
        if operation == 'get-download-url-for-layer': return {'downloadUrl': 'https://example.s3.amazonaws.com/config?secret=do-not-print'}
        pytest.fail('Unexpected AWS call')
    rt.aws = aws
    def download(*args, **kwargs):
        if mutation == 'download-error': raise OSError('https://secret-url')
        return io.BytesIO(b'other' if mutation == 'digest' else raw)
    monkeypatch.setattr(release, 'urlopen', download)
    with pytest.raises(release.MigrationError) as exc: release.verify_p20_fixture_image_config(rt, rt.outputs)
    assert 'secret' not in str(exc.value)


@pytest.mark.parametrize('mutation', ['none', 'template', 'digest', 'definition', 'capacity', 'host', 'extra-task', 'public-subnet', 'snapshot'])
def test_baseline_must_preserve_mixed_images_counts_definitions_and_clone(tmp_path, monkeypatch, mutation):
    rt = FixtureRuntime(tmp_path)
    p, out = rt.plan, rt.outputs
    out.update(EcsDesiredCount='1', EcsDatabaseHost='clone.internal', RdsEndpoint='original.internal',
               EcsMigrationImageTag=p['candidate_tag'], KeycloakDbName='sagrilaft', P20VpcId='vpc-p20')
    for kind, key in release.SERVICES.items(): out[key] = kind
    db = {'host': 'clone.internal', 'kmsKeyArn': 'arn:kms-p20'}
    snapshots = [{'DBSnapshotIdentifier': p['recovery_snapshot_identifier'], 'Status': 'available',
                  'Encrypted': True, 'KmsKeyId': db['kmsKeyArn']}]
    services = [{'serviceName': kind, 'desiredCount': 1, 'taskDefinition': p['baseline_task_definitions'][kind],
                 'verifiedTasks': [{'taskArn': kind, 'imageDigest': p['backend_image_digest'] if kind == 'backend' else p['previous_digests'][kind]}],
                 'networkConfiguration': {'awsvpcConfiguration': rt.network}} for kind in release.SERVICES]
    monkeypatch.setattr(release, 'stack_state', lambda runtime: out)
    monkeypatch.setattr(release, 'deployed_template', lambda runtime: {'Resources': {'unexpected': {}}} if mutation == 'template' else {'Resources': {}})
    monkeypatch.setattr(release, 'verify_restored_database', lambda *args: db)
    monkeypatch.setattr(release, 'verify_p20_clone_network_and_kms', lambda *args: {})
    def mixed_services(runtime, outputs, tag, count, image_tags=None):
        assert tag == p['previous_tag'] and image_tags == {'backend': p['backend_image_tag']}
        return services
    monkeypatch.setattr(release, 'services', mixed_services)
    monkeypatch.setattr(release, 'verify_p20_task_database_and_secret_scope', lambda *args: {})
    monkeypatch.setattr(release, 'verify_p20_target_health', lambda *args: [])
    monkeypatch.setattr(release, 'verify_tag_digests', lambda *args: None)
    monkeypatch.setattr(release, 'verify_p20_backend_image', lambda *args: None)
    monkeypatch.setattr(release, 'migration_environment', lambda *args: {
        'name': 'migration', 'image': out['EcrBackendUri'] + ':' + p['candidate_tag'], 'environment': [
            {'name': 'GIT_SHA', 'value': p['candidate_tag']}, {'name': 'RUN_MODE', 'value': 'migrate'},
            {'name': 'ZOHO_SIGN_ENABLED', 'value': 'false'}, {'name': 'P20_RUN_ID', 'value': p['environment']}]})
    if mutation == 'digest': services[0]['verifiedTasks'][0]['imageDigest'] = 'sha256:' + 'd' * 64
    if mutation == 'definition': services[0]['taskDefinition'] += '9'
    if mutation == 'capacity': services[0]['desiredCount'] = 2
    if mutation == 'host': out['EcsDatabaseHost'] = 'original.internal'
    if mutation == 'snapshot': snapshots[0]['Status'] = 'creating'
    original = rt.aws
    def aws(service, operation, *args):
        if operation == 'describe-db-snapshots': return {'DBSnapshots': snapshots}
        if operation == 'list-tasks':
            status = args[args.index('--desired-status') + 1]
            tasks = list(release.SERVICES) if status == 'RUNNING' else []
            if mutation == 'extra-task' and status == 'RUNNING': tasks.append('unrelated')
            return {'taskArns': tasks}
        if operation == 'describe-subnets':
            return {'Subnets': [{'VpcId': 'vpc-p20', 'MapPublicIpOnLaunch': mutation == 'public-subnet'}]}
        return original(service, operation, *args)
    rt.aws = aws
    if mutation == 'none':
        assert release.p20_scenario_a_baseline(rt) == (out, rt.network)
    else:
        with pytest.raises(release.MigrationError): release.p20_scenario_a_baseline(rt)
    assert not rt.locked


@pytest.mark.parametrize('attempt', ['deploy', 'real-migration', 'repeat-run'])
def test_fixture_boundary_rejects_additional_mutations(fixture_runtime, monkeypatch, attempt):
    def unsafe(aws, emit):
        if attempt == 'deploy': return aws('cloudformation', 'update-stack')
        p, out, network = fixture_runtime.plan, fixture_runtime.outputs, fixture_runtime.network
        args = ['--cluster', f"arn:aws:ecs:{p['region']}:{p['account']}:cluster/{out['EcsClusterName']}",
                '--launch-type', 'FARGATE', '--count', '1', '--task-definition', out['EcsMigrationTaskDefinitionArn'],
                '--client-token', os.environ['ECS_MIGRATION_CLIENT_TOKEN'], '--network-configuration', json.dumps({
                    'awsvpcConfiguration': {'subnets': network['subnets'], 'securityGroups': [out['EcsSecurityGroupId']], 'assignPublicIp': 'DISABLED'}}),
                '--overrides', json.dumps({'containerOverrides': [{'name': 'migration',
                    'command': ['python', 'scripts/p20_fail_before_ddl.py'], 'environment': [
                        {'name': 'P20_LAB_RUN_ID', 'value': p['environment']}, {'name': 'RUN_MODE', 'value': 'p20-fixture'}]}]})]
        if attempt == 'real-migration': args[-1] = json.dumps({'containerOverrides': [{'name': 'migration', 'command': ['alembic', 'upgrade', 'head']}]})
        aws('ecs', 'run-task', *args)
        return aws('ecs', 'run-task', *args)
    monkeypatch.setattr(release, 'run_migration', unsafe)
    with pytest.raises(release.MigrationError): release.coordinate(fixture_runtime, True)
    assert sum(op == 'run-task' for _, op, _ in fixture_runtime.calls) == (1 if attempt == 'repeat-run' else 0)
    assert fixture_runtime.locked
