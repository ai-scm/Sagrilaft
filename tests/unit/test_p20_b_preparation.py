"""Local B safety: no AWS, no real RDS, isolated additive history and health failure."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
import http.client

import pytest
import sqlalchemy as sa
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[2]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

migration = module('p20_b_migrate', 'backend/scripts/p20_b_migrate.py')
health = module('p20_b_unhealthy', 'backend/scripts/p20_b_unhealthy.py')
prepare = module('prepare_p20_b', 'scripts/prepare_p20_b.py')
LAB = 'p20-012345abcdef'
IDENTIFIER = LAB + '-c7-test-20261012'
HOST = IDENTIFIER + '.abc123.us-east-1.rds.amazonaws.com'
ENV = {'P20_RUN_ID': LAB, 'DATABASE_HOST': HOST, 'DATABASE_NAME': 'sagrilaft', 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-b-migration'}


@pytest.mark.parametrize('key,value', [('P20_RUN_ID', 'staging'), ('P20_RUN_ID', 'prod'), ('DATABASE_HOST', 'original.internal'), ('DATABASE_NAME', 'production'), ('RUN_MODE', 'migrate'), ('ZOHO_SIGN_ENABLED', 'true'), ('DATABASE_URL', 'postgresql://u:p@original.internal/sagrilaft')])
def test_migration_rejects_unsafe_destination_before_connect(key, value):
    env = dict(ENV, **{key: value})
    with pytest.raises(RuntimeError): migration.validate_target(env, IDENTIFIER, HOST)


def test_migration_refuses_reference_and_other_run():
    for identifier in [LAB + '-restore-20261009c', 'p20-ffffffffffff-c7-test-20261012']:
        with pytest.raises(RuntimeError): migration.validate_target(ENV, identifier, HOST)


def test_offline_ddl_only_adds_nullable_column_and_separate_revision(monkeypatch):
    monkeypatch.setattr(sa, 'create_engine', lambda *a, **k: pytest.fail('Offline must not connect'))
    output = io.StringIO()
    with redirect_stdout(output): migration.run_alembic(offline=True)
    sql = output.getvalue()
    assert 'ALTER TABLE public.formularios ADD COLUMN p20_b_probe VARCHAR(64)' in sql
    assert 'public.p20_b_alembic_version' in sql and 'p20b_expand_01' in sql
    assert 'DROP' not in sql and 'accesos_manuales' not in sql and 'f8a9b0c1d2e3' not in sql
    assert 'UPDATE public.alembic_version' not in sql
    assert 'downgrade' in migration.MIGRATION


@pytest.mark.parametrize('key,value', [('P20_RUN_ID', 'prod'), ('P20_RUN_ID', 'staging'), ('DATABASE_HOST', 'original.internal'), ('RUN_MODE', 'server'), ('ZOHO_SIGN_ENABLED', 'true'), ('P20_B_FORCE_UNHEALTHY', 'false')])
def test_health_fixture_refuses_to_start_outside_p20(key, value):
    env = dict(ENV, RUN_MODE='p20-b-unhealthy', P20_B_FORCE_UNHEALTHY='true')
    with pytest.raises(RuntimeError): health.validate(dict(env, **{key: value}))


def test_health_returns_503_without_importing_application_or_database():
    server = health.make_server('127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path in ['/health', '/', '/api/formularios/']:
            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            client.request('GET', path)
            result = client.getresponse()
            assert result.status == 503 and json.loads(result.read())['databaseTouched'] is False
            client.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def inputs():
    image = '874641912777.dkr.ecr.us-east-1.amazonaws.com/sagrilaft-' + LAB + '-backend'
    secret = 'arn:aws:secretsmanager:us-east-1:874641912777:secret:sagrilaft/' + LAB + '/db_credentials-abc'
    outputs = {'EcsClusterName': 'sagrilaft-' + LAB, 'EcsDatabaseHost': HOST, 'RdsEndpoint': 'original.internal', 'EcsDesiredCount': '1', 'EcrBackendUri': image, 'DbSecretArn': secret,
               'EcsMigrationTaskDefinitionArn': 'arn:aws:ecs:us-east-1:874641912777:task-definition/sagrilaft-' + LAB + '-migration:4'}
    resources = {'db': {'Type': 'AWS::RDS::DBInstance', 'Properties': {'DBInstanceClass': 'db.t3.medium'}}}
    for name in ['backend', 'frontend', 'portal', 'keycloak', 'migration']:
        env = [{'Name': k, 'Value': v} for k, v in dict(ENV, RUN_MODE='server').items()] if name == 'backend' else []
        if name in ('backend', 'migration'): env += [{'Name': 'KEYCLOAK_DB_URL', 'Value': f'jdbc:postgresql://{HOST}:5432/sagrilaft'}]
        if name == 'migration': env += [{'Name': 'DATABASE_HOST', 'Value': HOST}]
        if name == 'keycloak': env += [{'Name': 'KC_DB_URL', 'Value': f'jdbc:postgresql://{HOST}:5432/sagrilaft'}]
        resources[name] = {'Type': 'AWS::ECS::TaskDefinition', 'Properties': {'ContainerDefinitions': [{'Name': name, 'Image': image + ':' + name, 'Command': ['sh', 'entrypoint.sh'], 'Environment': env}]}}
        if name != 'migration':resources[name + '-service'] = {'Type': 'AWS::ECS::Service', 'Properties': {'DesiredCount': 1, 'DeploymentConfiguration': {'DeploymentCircuitBreaker': {'Enable': True, 'Rollback': True}}}}
    definition = {'taskDefinitionArn': outputs['EcsMigrationTaskDefinitionArn'], 'taskRoleArn': 'arn:aws:iam::874641912777:role/SagrilaftStack-p20-task', 'executionRoleArn': 'arn:aws:iam::874641912777:role/SagrilaftStack-p20-exec', 'networkMode': 'awsvpc', 'requiresCompatibilities': ['FARGATE'], 'cpu': '512', 'memory': '1024', 'containerDefinitions': [{'name': 'migration', 'image': image + ':migration', 'environment': [], 'secrets': [{'name': 'DB_USER', 'valueFrom': secret + ':username::'}, {'name': 'DB_PASSWORD', 'valueFrom': secret + ':password::'}], 'logConfiguration': {'options': {'awslogs-group': f'/sagrilaft/{LAB}/ecs/migration'}}}]}
    return {'Resources': resources, 'Outputs': {'EcsDatabaseHost': {'Value': HOST}}}, outputs, definition


def test_prepare_preserves_all_other_resources_and_rollback_is_exact_baseline():
    baseline, outputs, definition = inputs()
    before = copy.deepcopy(baseline)
    artifacts = prepare.prepare(baseline, outputs, definition, 'sha256:' + '1' * 64, '-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----')
    candidate = artifacts['activate-unhealthy.template.json']
    assert baseline == before and artifacts['rollback-baseline.template.json'] == baseline
    assert {k for k in candidate['Resources'] if candidate['Resources'][k] != baseline['Resources'][k]} == {'backend'}
    assert artifacts['plan-b.json']['executionAuthorized'] is False
    assert artifacts['plan-b.json']['newImagesRequired'] is False
    td = artifacts['register-b-migration.json']
    assert td['family'] == 'sagrilaft-' + LAB + '-b-migration'
    assert len(td['containerDefinitions'][0]['secrets']) == 2


@pytest.mark.parametrize('mutation', ['keycloak', 'frontend', 'migration', 'count', 'db', 'secret', 'host'])
def test_transition_guard_rejects_changes_outside_backend_fixture(mutation):
    baseline, outputs, definition = inputs()
    bundle = prepare.prepare(baseline, outputs, definition, 'sha256:' + '1' * 64, '-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----')
    candidate = bundle['activate-unhealthy.template.json']
    original_command = copy.deepcopy(candidate['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Command'])
    if mutation in ('keycloak', 'frontend', 'migration'): candidate['Resources'][mutation]['Properties']['ContainerDefinitions'][0]['Image'] = 'wrong'
    if mutation == 'count': candidate['Resources']['backend-service']['Properties']['DesiredCount'] = 2
    if mutation == 'db': candidate['Resources']['db']['Properties']['DBInstanceClass'] = 'different'
    if mutation == 'secret': candidate['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Secrets'] = ['other']
    if mutation == 'host': candidate['Resources']['backend']['Properties']['ContainerDefinitions'][0]['Environment'].append({'Name': 'OTHER_DB', 'Value': 'staging'})
    with pytest.raises(ValueError): prepare.assert_b_transition(baseline, candidate, bundle['plan-b.json']['backendImage'], original_command)


def test_fixture_has_no_downgrade_path():
    namespace = {}
    exec(compile(migration.MIGRATION, 'p20_b_fixture_revision', 'exec'), namespace)
    with pytest.raises(RuntimeError, match='does not allow downgrade'):
        namespace['downgrade']()


@pytest.mark.parametrize('mutation', ['reference', 'role', 'credentials', 'entrypoint', 'circuit-breaker'])
def test_preparer_refuses_unsafe_source_evidence(mutation):
    baseline, outputs, definition = inputs()
    if mutation == 'reference': outputs['EcsDatabaseHost'] = LAB + '-restore-20261009c.abc.us-east-1.rds.amazonaws.com'
    if mutation == 'role': definition['executionRoleArn'] = 'arn:aws:iam::874641912777:role/staging-role'
    if mutation == 'credentials': definition['containerDefinitions'][0]['secrets'][0]['valueFrom'] = 'staging-secret'
    if mutation == 'entrypoint': baseline['Resources']['backend']['Properties']['ContainerDefinitions'][0]['EntryPoint'] = ['sh', 'entrypoint.sh']
    if mutation == 'circuit-breaker': baseline['Resources']['backend-service']['Properties']['DeploymentConfiguration']['DeploymentCircuitBreaker']['Rollback'] = False
    with pytest.raises(ValueError):
        prepare.prepare(baseline, outputs, definition, 'sha256:' + '1' * 64, '-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----')
