"""P20 C local safety tests. No AWS calls or project infrastructure mutations."""
import copy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import base64
import zlib
import pytest

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'docs/evidencia/p20-recuperacion/9c67b6ea6842'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    obj = importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

p = module('prepare_p20_c', 'scripts/prepare_p20_c.py')
f = module('p20_c_fixture', 'backend/scripts/p20_c_fixture.py')
g = module('p20_c_provision_inventory', 'backend/scripts/p20_c_provision_inventory.py')

def baseline():
    value = p.load(EV / 'scenario-b-formal-closure-20261014T165050Z/template.json')['TemplateBody']
    return json.loads(value) if isinstance(value, str) else value

def backend():
    return p.load(EV / 'scenario-b-functional-smoke-20261014T155828Z/backend-definition.json')['taskDefinition']

def controls():
    return {'mainRevision': 'c7a1c1a65662', 'bRevision': 'p20b_expand_01', 'formId': f.UID,
            'city': f.CITY, 'state': 'borrador', 'bProbe': None, 'tableCounts': {'formularios': 1}, 'incompatible': False}

def receipt():
    now = datetime.now(timezone.utc)
    names = [s['serviceName'] for s in p.load(EV / 'scenario-b-formal-closure-20261014T165050Z/services.json')['services']]
    return {'checkedAtUTC': now.isoformat(), 'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
            'stack': {'StackName': 'SagrilaftStack-' + p.LAB, 'StackStatus': 'UPDATE_COMPLETE'},
            'template': p.stopped_template(baseline()),
            'services': {'services': [{'serviceName': name, 'clusterArn': 'arn:aws:ecs:us-east-1:874641912777:cluster/sagrilaft-' + p.LAB,
                                      'desiredCount': 0, 'runningCount': 0, 'pendingCount': 0} for name in names]},
            'running': {'taskArns': []}, 'pending': {'taskArns': []}, 'activeOwnerProcesses': [], 'activeOperations': [],
            'lockHead': {'ETag': 'same'}, 'expectedLockETag': 'same', 'lockBody': {'runId': 'run-c', 'planHash': 'plan-c'},
            'database': {'DBInstanceIdentifier': p.WORK, 'Endpoint': {'Address': p.HOST}, 'DBInstanceStatus': 'available',
                         'StorageEncrypted': True, 'KmsKeyId': p.KMS, 'PubliclyAccessible': False,
                         'DBSubnetGroup': {'VpcId': p.VPC}, 'VpcSecurityGroups': [{'VpcSecurityGroupId': p.SG}]},
            'snapshot': {'DBSnapshotIdentifier': p.SNAPSHOT, 'DBInstanceIdentifier': p.WORK, 'Status': 'available',
                         'Encrypted': True, 'KmsKeyId': p.KMS, 'VpcId': p.VPC, 'Engine': 'postgres', 'EngineVersion': '16.13',
                         'SnapshotCreateTime': (now - timedelta(seconds=20)).isoformat()},
            'quiescedAtUTC': (now - timedelta(seconds=30)).isoformat(),
            'snapshotTags': [{'Key': 'Project', 'Value': 'sagrilaft'}, {'Key': 'Environment', 'Value': p.LAB}], 'controls': controls()}

def validate(r):
    names = [s['serviceName'] for s in receipt()['services']['services']]
    return p.validate_containment(r, 'run-c', 'plan-c', names, p.fingerprint(p.stopped_template(baseline())))


def test_containment_changes_only_four_counts_and_output():
    old = baseline();new = p.stopped_template(old)
    changed = {k for k in old['Resources'] if old['Resources'][k] != new['Resources'][k]}
    assert len(changed) == 4 and all(old['Resources'][k]['Type'] == 'AWS::ECS::Service' for k in changed)
    assert old['Outputs']['EcsDatabaseHost'] == new['Outputs']['EcsDatabaseHost']
    assert p.task_names(old) == p.task_names(new)


def test_repoint_preserves_all_images_secrets_and_capacity():
    old = p.stopped_template(baseline());host = p.RESTORE + '.verified.us-east-1.rds.amazonaws.com'
    new = p.repoint_template(old, host)
    changed = {k for k in old['Resources'] if old['Resources'][k] != new['Resources'][k]}
    assert changed == {p.task_names(old)[n][0] for n in ('backend', 'keycloak', 'migration')}
    for n, (_, c) in p.task_names(new).items():
        assert c['Image'] == p.task_names(old)[n][1]['Image'] and c.get('Secrets') == p.task_names(old)[n][1].get('Secrets')
    assert all(r['Properties']['DesiredCount'] == 0 for r in new['Resources'].values() if r['Type'] == 'AWS::ECS::Service')


def test_repoint_from_current_live_template_preserves_all_c_resources():
    live = p.load(EV / 'scenario-c-current-inventory-20261014T2259Z/live-template.json')['TemplateBody']
    host = p.RESTORE + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
    new = p.repoint_template_from_live(live, host)
    assert len(live['Resources']) == len(new['Resources']) == 157
    assert set(live['Resources']) == set(new['Resources'])
    assert new['Outputs']['EcsDesiredCount']['Value'] == '0'
    assert new['Outputs']['EcsDatabaseHost']['Value'] == host
    assert all(r['Properties']['DesiredCount'] == 0 for r in new['Resources'].values()
               if r['Type'] == 'AWS::ECS::Service')
    assert new == p.repoint_template_from_live(copy.deepcopy(live), host)


def test_repoint_from_current_live_template_rejects_historical_150_resource_base():
    live = baseline()
    for logical in list(live['Resources']):
        if logical.startswith(('EcsFargateCInventory', 'SecretsCInventory')):
            del live['Resources'][logical]
    with pytest.raises(ValueError):
        p.repoint_template_from_live(live, p.RESTORE + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com')


def test_live_repoint_receipt_pins_lock_restored_db_snapshot_and_controls():
    plan = p.load(EV / 'scenario-c-command-preparation-20261014T172904Z/artifacts/plan-c.json')
    live = p.load(EV / 'scenario-c-current-inventory-20261014T2259Z/live-template.json')['TemplateBody']
    db = restored_db()
    db.update({'DBInstanceIdentifier': p.RESTORE, 'Engine': 'postgres', 'EngineVersion': '16.13',
               'DBInstanceClass': 'db.t3.medium', 'AllocatedStorage': 100, 'StorageType': 'gp2',
               'BackupRetentionPeriod': 1, 'MultiAZ': False, 'TagList': [
                   {'Key': 'Project', 'Value': 'sagrilaft'}, {'Key': 'Environment', 'Value': p.LAB}]})
    rec = {'checkedAtUTC': datetime.now(timezone.utc).isoformat(), 'identity': {'Account': p.ACCOUNT},
           'region': 'us-east-1', 'stack': {'StackName': 'SagrilaftStack-' + p.LAB, 'StackStatus': 'UPDATE_COMPLETE'},
           'template': live, 'lockHead': {'ETag': 'etag-c'}, 'expectedLockETag': 'etag-c',
           'lockBody': {'runId': plan['runId'], 'planHash': plan['planHash']},
           'running': {'taskArns': []}, 'pending': {'taskArns': []},
           'services': {'services': [{'serviceName': name, 'desiredCount': 0, 'runningCount': 0, 'pendingCount': 0}
                       for name in plan['serviceNames']]},
           'restoredDatabase': db,
           'sourceSnapshot': {'DBSnapshotIdentifier': p.SNAPSHOT, 'Status': 'available', 'Encrypted': True,
                              'KmsKeyId': p.KMS, 'Engine': 'postgres', 'EngineVersion': '16.13'},
           'sourceSnapshotTags': [{'Key': 'Project', 'Value': 'sagrilaft'},
                                  {'Key': 'Environment', 'Value': p.LAB}, {'Key': 'Scenario', 'Value': 'C'}],
           'restoredControls': {**controls(), 'incompatible': False}}
    template, host = p.validate_repoint_receipt(rec, plan)
    target = p.repoint_template_from_live(template, host)
    assert len(target['Resources']) == 157
    assert p.validate_hosts(target, host) is None
    rec['lockHead']['ETag'] = 'changed'
    with pytest.raises(ValueError):p.validate_repoint_receipt(rec, plan)


@pytest.mark.parametrize('host', [p.HOST, 'staging.internal', p.RESTORE + '.x.eu-west-1.rds.amazonaws.com'])
def test_repoint_refuses_wrong_or_original_target(host):
    with pytest.raises(ValueError):p.repoint_template(p.stopped_template(baseline()), host)


def test_ddl_receipt_valid():
    assert len(validate(receipt())) == 64


@pytest.mark.parametrize('case', ['account', 'age', 'running', 'pending', 'operator', 'lock', 'backup-source', 'backup-age',
                                 'backup-encryption', 'backup-pending', 'city', 'main', 'services', 'clone', 'template'])
def test_ddl_receipt_rejects_unsafe_state(case):
    r = receipt()
    if case == 'account':r['identity']['Account'] = '000000000000'
    elif case == 'age':r['checkedAtUTC'] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    elif case == 'running':r['running']['taskArns'] = ['other']
    elif case == 'pending':r['pending']['taskArns'] = ['other']
    elif case == 'operator':r['activeOwnerProcesses'] = [123]
    elif case == 'lock':r['lockHead']['ETag'] = 'changed'
    elif case == 'backup-source':r['snapshot']['DBInstanceIdentifier'] = 'staging'
    elif case == 'backup-age':r['snapshot']['SnapshotCreateTime'] = '2020-01-01T00:00:00+00:00'
    elif case == 'backup-encryption':r['snapshot']['Encrypted'] = False
    elif case == 'backup-pending':r['snapshot']['Status'] = 'creating'
    elif case == 'city':r['controls']['city'] = 'unexpected'
    elif case == 'main':r['controls']['mainRevision'] = 'f8a9b0c1d2e3'
    elif case == 'services':r['services']['services'][0]['desiredCount'] = 1
    elif case == 'clone':r['database']['Endpoint']['Address'] = 'reference'
    elif case == 'template':r['template']['Outputs']['EcsDatabaseHost']['Value'] = 'reference'
    with pytest.raises(ValueError):validate(r)


@pytest.mark.parametrize('key,value', [('P20_RUN_ID', 'staging'), ('DATABASE_HOST', 'other'),
                                    ('ZOHO_SIGN_ENABLED', 'true'), ('RUN_MODE', 'migrate')])
def test_fixture_blocks_wrong_target_before_connection(key, value):
    env = {'P20_RUN_ID': p.LAB, 'DATABASE_HOST': p.HOST, 'DATABASE_NAME': 'sagrilaft',
           'DB_USER': 'p20_c_inventory', 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-c-fixture'}
    env[key] = value
    with pytest.raises(RuntimeError):f.validate_target(env, p.WORK, p.HOST, 'incompatibility', True, 'a' * 64)


def test_fixture_requires_validated_guard_hash():
    env = {'P20_RUN_ID': p.LAB, 'DATABASE_HOST': p.HOST, 'DATABASE_NAME': 'sagrilaft', 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-c-fixture'}
    with pytest.raises(RuntimeError):f.validate_target(env, p.WORK, p.HOST, 'incompatibility', True, 'a' * 64)
    env['P20_C_GUARD_SHA256'] = 'a' * 64
    f.validate_target(env, p.WORK, p.HOST, 'incompatibility', True, 'a' * 64)
    with pytest.raises(RuntimeError):f.validate_target(env, p.RESTORE, p.RESTORE + '.x.us-east-1.rds.amazonaws.com', 'incompatibility', True, 'a' * 64)


def test_inventory_requires_exact_postgres_readonly_username_and_no_database_url():
    env = {'P20_RUN_ID': p.LAB, 'DATABASE_HOST': p.HOST, 'DATABASE_NAME': 'sagrilaft',
           'DB_USER': 'p20_c_inventory', 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-c-fixture'}
    f.validate_target(env, p.WORK, p.HOST, 'inventory')
    env['DB_USER'] = 'sagrilaft_user'
    with pytest.raises(RuntimeError):f.validate_target(env, p.WORK, p.HOST, 'inventory')
    env['DB_USER'] = 'p20_c_inventory';env['DATABASE_URL'] = 'postgresql://other@staging/db'
    with pytest.raises(RuntimeError):f.validate_target(env, p.WORK, p.HOST, 'inventory')


def test_inventory_role_sql_grants_only_read_privileges_on_control_tables():
    role_sql = (ROOT / 'backend/scripts/p20_c_inventory_role.sql').read_text()
    assert 'NOSUPERUSER' in role_sql and 'NOCREATEDB' in role_sql and 'NOCREATEROLE' in role_sql
    assert 'NOREPLICATION' in role_sql and 'NOBYPASSRLS' in role_sql and 'NOINHERIT' in role_sql
    assert 'GRANT SELECT (version_num) ON TABLE public.alembic_version' in role_sql
    assert 'GRANT SELECT (version_num) ON TABLE public.p20_b_alembic_version' in role_sql
    assert 'GRANT SELECT (id, razon_social, ciudad, estado, p20_b_probe)' in role_sql
    assert 'public.alembic_version' in role_sql
    assert 'public.p20_b_alembic_version' in role_sql
    assert 'public.formularios' in role_sql
    assert not re.search(r'\bGRANT\s+(INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER|CREATE|ALL)\b', role_sql, re.I)
    assert '\\password p20_c_inventory' in role_sql
def test_backend_boot_has_tls_and_no_migration_entrypoint():
    assert "'sslmode':'verify-full'" in p.BACKEND_BOOT and "'uvicorn'" in p.BACKEND_BOOT
    assert 'entrypoint.sh' not in p.BACKEND_BOOT and 'alembic' not in p.BACKEND_BOOT
    assert "os.environ.get('RUN_MODE')=='server'" in p.BACKEND_BOOT


def registered_pair():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    requested = p.definition(backend(), p.HOST, ca, 'backend-incompatible')
    actual = copy.deepcopy(requested);actual.update(status='ACTIVE', taskDefinitionArn='arn:aws:ecs:us-east-1:874641912777:task-definition/' + requested['family'] + ':1')
    return requested, actual


def test_registered_environment_order_is_not_a_change():
    req, actual = registered_pair();actual['containerDefinitions'][0]['environment'].reverse()
    assert p.validate_registered_definition(actual, req).endswith(':1')


def test_inventory_definition_bypasses_image_entrypoint_and_runs_read_only_fixture():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    secret = f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-AbCd1234'
    security = {'taskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-task',
                'executionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-execution',
                'secretArn': secret}
    task = p.definition(backend(), p.HOST, ca, 'inventory', Path(f.__file__).read_text(), 'inventory',
                        inventory_security=security)
    container = task['containerDefinitions'][0]
    assert container['entryPoint'][0:2] == ['/usr/local/bin/python', '-c']
    assert container['command'] == ['P20_C_INVENTORY']
    assert container['portMappings'] == []
    encoded = re.search(r"b64decode\('([A-Za-z0-9+/=]+)'\)", container['entryPoint'][2]).group(1)
    source = zlib.decompress(base64.b64decode(encoded)).decode()
    assert "'inventory', '--db-identifier', '" + p.WORK + "'" in container['entryPoint'][2]
    assert "'--query'" in container['entryPoint'][2]
    assert p.HOST in container['entryPoint'][2] and p.WORK in container['entryPoint'][2]
    assert "sslmode='verify-full'" in source and 'sslrootcert=' in source
    assert 'alembic upgrade' not in source and 'entrypoint.sh' not in source and 'uvicorn' not in source
    assert task['taskRoleArn'] == security['taskRoleArn']
    assert task['executionRoleArn'] == security['executionRoleArn']
    assert container['secrets'] == [
        {'name': 'DB_USER', 'valueFrom': secret + ':username::'},
        {'name': 'DB_PASSWORD', 'valueFrom': secret + ':password::'}]
    assert {item['name'] for item in container['environment']} == {
        'DATABASE_NAME', 'DATABASE_HOST', 'P20_RUN_ID', 'RUN_MODE', 'ZOHO_SIGN_ENABLED'}
    assert 'SNS_TOPIC_ARN' not in {item['name'] for item in container['environment']}
    fixture_source = Path(f.__file__).read_text()
    assert "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in fixture_source
    assert "default_transaction_read_only=on" in fixture_source
    assert 'SELECT count(*)' not in fixture_source
    assert f.validate_target({'P20_RUN_ID': p.LAB, 'DATABASE_HOST': p.HOST, 'DATABASE_NAME': 'sagrilaft',
                              'DB_USER': 'p20_c_inventory', 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-c-fixture'},
                             p.WORK, p.HOST, 'inventory') is None


@pytest.mark.parametrize('override', [['P20_C_INVENTORY'], ['P20_C_DDL'], ['--apply'],
                                      ['-c', 'print("app")'], [], ['P20_C_INVENTORY', '--apply']])
def test_inventory_entrypoint_rejects_command_overrides_except_fixed_sentinel(override):
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    fixture_source = '''import argparse
parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['inventory'])
parser.add_argument('--query', action='store_true', required=True)
args = parser.parse_args()
print('INVENTORY_BODY_REACHED:' + args.action)
'''
    fixed = p.guarded_fixture_entrypoint(fixture_source, ca,
                                         ['inventory', '--query'], 'P20_C_INVENTORY')
    proc = subprocess.run([sys.executable, *fixed[1:], *override], capture_output=True, text=True, check=False)
    if override == ['P20_C_INVENTORY']:
        assert proc.returncode == 0 and 'INVENTORY_BODY_REACHED:inventory' in proc.stdout
    else:
        assert proc.returncode != 0
        assert 'P20-C rejected command override' in proc.stderr


def test_provisioner_entrypoint_preserves_sentinel_and_required_target_arguments():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    fixture_source = '''import argparse
parser = argparse.ArgumentParser()
parser.add_argument('sentinel', choices=['P20_C_PROVISION_INVENTORY'])
parser.add_argument('--expected-db-identifier', required=True)
parser.add_argument('--expected-host', required=True)
parser.add_argument('--ssl-root-cert', required=True)
args = parser.parse_args()
print('PROVISIONER_ARGS_ACCEPTED:' + args.sentinel + ':' + args.expected_db_identifier)
'''
    args = ['--expected-db-identifier', p.WORK, '--expected-host', p.HOST,
            '--ssl-root-cert', '/tmp/p20-c-ca.pem']
    fixed = p.guarded_fixture_entrypoint(fixture_source, ca, args, 'P20_C_PROVISION_INVENTORY',
                                         include_sentinel=True)
    proc = subprocess.run([sys.executable, *fixed[1:], 'P20_C_PROVISION_INVENTORY'],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert f'PROVISIONER_ARGS_ACCEPTED:P20_C_PROVISION_INVENTORY:{p.WORK}' in proc.stdout

    rejected = subprocess.run([sys.executable, *fixed[1:], 'P20_C_INVENTORY'],
                              capture_output=True, text=True, check=False)
    assert rejected.returncode != 0
    assert 'P20-C rejected command override' in rejected.stderr


def provisioner_task():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    prefix = f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/'
    security = {
        'taskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-provision-task',
        'executionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-provision-execution',
        'adminSecretArn': prefix + 'db_credentials-AbCd1234',
        'inventorySecretArn': prefix + 'c_inventory_db_credentials-XyZ9876',
    }
    return p.definition(backend(), p.HOST, ca, 'inventory-provisioner',
                        Path(g.__file__).read_text(), 'provision-inventory', provision_security=security)


def test_provisioner_definition_is_one_shot_pinned_to_clone_and_two_secrets():
    task = provisioner_task()
    c = task['containerDefinitions'][0]
    assert task['family'] == f'sagrilaft-{p.LAB}-c-inventory-provisioner'
    assert task['taskRoleArn'].endswith('-c-inventory-provision-task')
    assert task['executionRoleArn'].endswith('-c-inventory-provision-execution')
    assert c['command'] == ['P20_C_PROVISION_INVENTORY'] and c['portMappings'] == []
    assert {s['name']: s['valueFrom'] for s in c['secrets']} == {
        'DB_ADMIN_USER': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/db_credentials-AbCd1234:username::',
        'DB_ADMIN_PASSWORD': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/db_credentials-AbCd1234:password::',
        'INVENTORY_DB_USER': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-XyZ9876:username::',
        'INVENTORY_DB_PASSWORD': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-XyZ9876:password::',
    }
    env = {item['name']: item['value'] for item in c['environment']}
    assert env['DATABASE_HOST'] == p.HOST and env['EXPECTED_DB_IDENTIFIER'] == p.WORK
    assert env['RUN_MODE'] == 'p20-c-provisioner' and env['ZOHO_SIGN_ENABLED'] == 'false'
    assert 'DATABASE_URL' not in env and 'DB_PASSWORD' not in env
    assert 'uvicorn' not in json.dumps(c) and 'entrypoint.sh' not in json.dumps(c)
    assert p.validate_inventory_provisioner_request(task)


@pytest.mark.parametrize('mutation', ['command', 'entrypoint', 'host', 'secret', 'task-role', 'extra-env'])
def test_provisioner_definition_rejects_drift_and_command_injection(mutation):
    task = provisioner_task()
    c = task['containerDefinitions'][0]
    if mutation == 'command': c['command'] = ['P20_C_INVENTORY']
    elif mutation == 'entrypoint': c['entryPoint'] = ['sh', 'entrypoint.sh']
    elif mutation == 'host': c['environment'][1]['value'] = 'staging.example'
    elif mutation == 'secret': c['secrets'][0]['valueFrom'] = 'arn:aws:secretsmanager:us-east-1:874641912777:secret:prod'
    elif mutation == 'task-role': task['taskRoleArn'] = backend()['taskRoleArn']
    elif mutation == 'extra-env': c['environment'].append({'name': 'DATABASE_URL', 'value': 'postgresql://prod'})
    with pytest.raises(ValueError): p.validate_inventory_provisioner_request(task)


def test_registered_provisioner_definition_is_revalidated_including_fixed_command():
    requested = provisioner_task()
    actual = copy.deepcopy(requested)
    actual.update(status='ACTIVE', taskDefinitionArn=(
        'arn:aws:ecs:us-east-1:874641912777:task-definition/' + requested['family'] + ':1'))
    assert p.validate_registered_definition(actual, requested).endswith(':1')
    actual['containerDefinitions'][0]['command'] = ['P20_C_INVENTORY']
    with pytest.raises(ValueError): p.validate_registered_definition(actual, requested)


def test_provisioner_credentials_and_target_guards_and_scram_verifier():
    env = {'P20_RUN_ID': g.LAB, 'RUN_MODE': 'p20-c-provisioner', 'ZOHO_SIGN_ENABLED': 'false',
           'EXPECTED_DB_IDENTIFIER': g.DB_ID, 'DATABASE_HOST': g.DB_HOST, 'DATABASE_NAME': g.DB_NAME,
           'DB_ADMIN_USER': g.ADMIN_USER, 'EXPECTED_DB_ADMIN_USER': g.ADMIN_USER,
           'INVENTORY_DB_USER': g.INVENTORY_USER, 'DB_ADMIN_PASSWORD': 'admin-secret',
           'INVENTORY_DB_PASSWORD': 'A' * 32}
    assert g.validate_environment(env) is None
    for key, value in [('DATABASE_HOST', 'staging.example'), ('RUN_MODE', 'server'),
                       ('ZOHO_SIGN_ENABLED', 'true'), ('EXPECTED_DB_IDENTIFIER', 'wrong-db')]:
        changed = dict(env);changed[key] = value
        with pytest.raises(RuntimeError): g.validate_environment(changed)
    changed = dict(env);changed['DATABASE_URL'] = 'postgresql://prod'
    with pytest.raises(RuntimeError): g.validate_environment(changed)
    verifier = g.scram_verifier('A' * 32, salt=b'0123456789abcdef')
    assert re.fullmatch(r'SCRAM-SHA-256\$4096:[A-Za-z0-9+/]{22}==\$[A-Za-z0-9+/]{43}=:[A-Za-z0-9+/]{43}=', verifier)
    assert 'A' * 32 not in verifier


def test_provisioner_database_receipt_pins_private_encrypted_clone():
    proof = {'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
             'database': {'DBInstanceIdentifier': p.WORK, 'DBInstanceStatus': 'available',
                          'StorageEncrypted': True, 'PubliclyAccessible': False,
                          'Endpoint': {'Address': p.HOST}, 'DBSubnetGroup': {'VpcId': p.VPC},
                          'VpcSecurityGroups': [{'VpcSecurityGroupId': p.SG}]}}
    assert p.validate_inventory_provisioner_database_receipt(proof) is None
    for path, value in [('identity.Account', '000000000000'), ('database.DBInstanceIdentifier', 'original-db'),
                        ('database.DBInstanceStatus', 'modifying'), ('database.StorageEncrypted', False),
                        ('database.PubliclyAccessible', True), ('database.Endpoint.Address', 'staging.host'),
                        ('database.DBSubnetGroup.VpcId', 'vpc-other'),
                        ('database.VpcSecurityGroups', [{'VpcSecurityGroupId': 'sg-other'}])]:
        bad = copy.deepcopy(proof)
        target = bad
        parts = path.split('.')
        for key in parts[:-1]: target = target[key]
        target[parts[-1]] = value
        with pytest.raises(ValueError): p.validate_inventory_provisioner_database_receipt(bad)


@pytest.mark.parametrize('security', [None, {},
    {'taskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/SagrilaftStack-p20-backend',
     'executionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-execution',
     'secretArn': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-AbCd1234'}])
def test_inventory_definition_requires_exact_dedicated_role_and_secret(security):
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    with pytest.raises(ValueError):
        p.definition(backend(), p.HOST, ca, 'inventory', Path(f.__file__).read_text(), 'inventory',
                     inventory_security=security)


def test_inventory_task_registration_pins_direct_python_entrypoint():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    secret = f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-AbCd1234'
    security = {'taskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-task',
                'executionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-execution',
                'secretArn': secret}
    req = p.definition(backend(), p.HOST, ca, 'inventory', Path(f.__file__).read_text(), 'inventory',
                       inventory_security=security)
    actual = copy.deepcopy(req)
    actual.update(status='ACTIVE', taskDefinitionArn='arn:aws:ecs:us-east-1:874641912777:task-definition/' + req['family'] + ':1')
    assert p.validate_registered_definition(actual, req).endswith(':1')
    altered = copy.deepcopy(actual)
    altered['containerDefinitions'][0]['command'] = ['-c', 'print("start app")']
    with pytest.raises(ValueError):p.validate_registered_definition(altered, req)
    forged_request = copy.deepcopy(req)
    forged_request['containerDefinitions'][0]['entryPoint'][2] += '; print("not inventory")'
    forged_actual = copy.deepcopy(actual)
    forged_actual['containerDefinitions'][0]['entryPoint'] = forged_request['containerDefinitions'][0]['entryPoint']
    with pytest.raises(ValueError):p.validate_registered_definition(forged_actual, forged_request)


def test_readonly_inventory_can_target_exact_restored_rds_but_not_change_fixture_action():
    ca = (EV / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    secret = f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-AbCd1234'
    security = {'taskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-task',
                'executionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-execution',
                'secretArn': secret}
    host = p.RESTORE + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
    req = p.definition(backend(), host, ca, 'inventory', Path(f.__file__).read_text(), 'inventory',
                       inventory_security=security)
    assert p.validate_inventory_request(req)
    container = req['containerDefinitions'][0]
    assert container['command'] == ['P20_C_INVENTORY']
    assert container['environment'] == [
        {'name': 'DATABASE_NAME', 'value': 'sagrilaft'},
        {'name': 'DATABASE_HOST', 'value': host},
        {'name': 'P20_RUN_ID', 'value': p.LAB},
        {'name': 'RUN_MODE', 'value': 'p20-c-fixture'},
        {'name': 'ZOHO_SIGN_ENABLED', 'value': 'false'},
    ]
    source = Path(f.__file__).read_text()
    env = {'P20_RUN_ID': p.LAB, 'ZOHO_SIGN_ENABLED': 'false', 'RUN_MODE': 'p20-c-fixture',
           'DATABASE_HOST': host, 'DATABASE_NAME': 'sagrilaft', 'DB_USER': 'p20_c_inventory'}
    assert f.validate_target(env, p.RESTORE, host, 'inventory') is None
    with pytest.raises(RuntimeError):
        f.validate_target({**env, 'DATABASE_HOST': p.HOST}, p.RESTORE, host, 'inventory')
    for action in ('incompatibility', 'verify-incompatible'):
        with pytest.raises(RuntimeError):
            f.validate_target({'P20_RUN_ID': p.LAB, 'ZOHO_SIGN_ENABLED': 'false',
                               'RUN_MODE': 'p20-c-fixture', 'DATABASE_HOST': host,
                               'DATABASE_NAME': 'sagrilaft'}, p.RESTORE, host, action)


@pytest.mark.parametrize('case', ['command', 'secret', 'host', 'entrypoint', 'role', 'image', 'family', 'port'])
def test_registration_binding_blocks_unexpected_changes(case):
    req, actual = registered_pair();c = actual['containerDefinitions'][0]
    if case == 'command':c['command'] = ['sh', 'entrypoint.sh']
    elif case == 'secret':c['secrets'][0]['valueFrom'] = 'staging'
    elif case == 'host':next(e for e in c['environment'] if e['name'] == 'DATABASE_HOST')['value'] = 'reference'
    elif case == 'entrypoint':c['entryPoint'] = ['sh']
    elif case == 'role':actual['taskRoleArn'] = 'arn:aws:iam::111111111111:role/other'
    elif case == 'image':c['image'] = 'other'
    elif case == 'family':actual['family'] = 'staging'
    elif case == 'port':c['portMappings'] = [{'containerPort': 8000}]
    with pytest.raises(ValueError):p.validate_registered_definition(actual, req)


@pytest.fixture
def local_pg():
    import os
    import psycopg
    from psycopg import sql
    folder = os.environ.get('P20_C_LOCAL_PG_SOCKET', '')
    if not folder:pytest.skip('Explicit disposable local Unix socket required')
    assert folder.startswith('/tmp/p20-c-pg-') and (Path(folder) / 'data/PG_VERSION').is_file()
    name = 'p20_c_' + uuid.uuid4().hex
    args = {'host': folder, 'port': 55482, 'user': 'p20_c_local', 'dbname': 'postgres', 'autocommit': True}
    admin = psycopg.connect(**args);admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    conn = psycopg.connect(**{**args, 'dbname': name})
    try:
        conn.execute('CREATE TABLE alembic_version(version_num text); INSERT INTO alembic_version VALUES (\'c7a1c1a65662\')')
        conn.execute('CREATE TABLE p20_b_alembic_version(version_num text); INSERT INTO p20_b_alembic_version VALUES (\'p20b_expand_01\')')
        conn.execute('CREATE TABLE formularios(id text PRIMARY KEY, razon_social text, ciudad text, estado text, p20_b_probe varchar(64))')
        conn.execute('INSERT INTO formularios VALUES(%s,%s,%s,%s,%s)', (f.UID, f.MARKER, f.CITY, 'borrador', 'preserved'))
        yield conn
    finally:
        conn.close();admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)));admin.close()


def test_postgres_rename_has_real_42703_and_preserves_controls(local_pg):
    import psycopg
    before = f.controls(local_pg)
    with local_pg.transaction():after = f.apply_connection(local_pg)
    assert before['tableCounts'] == after['tableCounts'] and after['bProbe'] == 'preserved'
    with pytest.raises(psycopg.errors.UndefinedColumn):local_pg.execute('SELECT razon_social FROM formularios')
    assert f.controls(local_pg, incompatible=True)['incompatible'] is True


def test_postgres_exception_rolls_back_rename(local_pg):
    with pytest.raises(RuntimeError):
        with local_pg.transaction():
            f.apply_connection(local_pg)
            raise RuntimeError('abort before commit')
    assert f.controls(local_pg)['incompatible'] is False


def test_postgres_wrong_control_refuses_before_ddl(local_pg):
    local_pg.execute('UPDATE formularios SET ciudad=%s', ('unexpected',))
    with pytest.raises(RuntimeError):
        with local_pg.transaction():f.apply_connection(local_pg)
    assert local_pg.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='formularios' AND column_name='razon_social'").fetchone()[0] == 1


def restored_db():
    db = copy.deepcopy(receipt()['database'])
    db.update(DBInstanceIdentifier=p.RESTORE, Endpoint={'Address': p.RESTORE + '.verified.us-east-1.rds.amazonaws.com'},
              Engine='postgres', EngineVersion='16.13', DBInstanceClass='db.t3.medium', AllocatedStorage=100,
              StorageType='gp2', BackupRetentionPeriod=1, MultiAZ=False,
              TagList=[{'Key': 'Project', 'Value': 'sagrilaft'}, {'Key': 'Environment', 'Value': p.LAB}])
    return db


@pytest.mark.parametrize('case', ['initializing', 'public', 'kms', 'sg', 'id', 'tags', 'retention'])
def test_restore_identity_network_encryption_readiness(case):
    db = restored_db()
    assert p.restored_host(db).startswith(p.RESTORE + '.')
    if case == 'initializing':db['StorageOperationStatus'] = 'Initializing'
    elif case == 'public':db['PubliclyAccessible'] = True
    elif case == 'kms':db['KmsKeyId'] = 'other'
    elif case == 'sg':db['VpcSecurityGroups'][0]['VpcSecurityGroupId'] = 'shared'
    elif case == 'id':db['DBInstanceIdentifier'] = p.WORK
    elif case == 'tags':db['TagList'] = []
    elif case == 'retention':db['BackupRetentionPeriod'] = 0
    with pytest.raises(ValueError):p.restored_host(db)


def test_restore_receipt_requires_matching_snapshot_controls():
    r = receipt();r['controls']['incompatible'] = True
    names = [s['serviceName'] for s in r['services']['services']]
    plan = {'runId': 'run-c', 'planHash': 'plan-c', 'serviceNames': names,
            'stoppedTemplateSha256': p.fingerprint(p.stopped_template(baseline()))}
    request = {'DBSnapshotIdentifier': p.SNAPSHOT, 'DBInstanceIdentifier': p.RESTORE}
    actual = {'restoreRequest': request, 'database': restored_db(), 'snapshot': r['snapshot'],
              'snapshotControls': controls(), 'restoredControls': controls(), 'containment': r}
    assert p.validate_restore_receipt(actual, request, plan).startswith(p.RESTORE)
    actual['restoredControls']['tableCounts']['formularios'] = 0
    with pytest.raises(ValueError):p.validate_restore_receipt(actual, request, plan)
    actual['restoredControls'] = {};actual['snapshotControls'] = {}
    with pytest.raises(ValueError):p.validate_restore_receipt(actual, request, plan)


@pytest.mark.parametrize('phase', ['stop', 'repoint'])
def test_change_set_scope_refuses_unrelated_or_replaced_service(phase):
    b = baseline()
    ids = ({k for k,r in b['Resources'].items() if r['Type']=='AWS::ECS::Service'} if phase=='stop' else
           {p.task_names(b)[n][0] for n in ('backend','keycloak','migration')} |
           {k for k,r in b['Resources'].items() if r['Type']=='AWS::ECS::Service' and any(n in k for n in ('BackendService','KeycloakService'))})
    cs = {'StackName':'SagrilaftStack-'+p.LAB,'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE',
          'Changes':[{'ResourceChange':{'LogicalResourceId':k,'ResourceType':b['Resources'][k]['Type'],'Action':'Modify',
          'Replacement':'True' if b['Resources'][k]['Type']=='AWS::ECS::TaskDefinition' else 'False'}} for k in ids]}
    assert p.validate_change_set(cs,b,phase)
    cs['Changes'].append({'ResourceChange':{'LogicalResourceId':'UnexpectedRDS','ResourceType':'AWS::RDS::DBInstance','Action':'Modify','Replacement':'True'}})
    with pytest.raises(ValueError):p.validate_change_set(cs,b,phase)


def actual_containment_change_set():
    return p.load(EV / 'scenario-c-containment-20261014T174924Z/blocked-final-change-set.json')


def test_actual_containment_accepts_only_reviewed_dynamic_dependencies():
    b=baseline();target=p.stopped_template(b);cs=actual_containment_change_set()
    assert p.validate_change_set(cs,b,'stop',target)
    with pytest.raises(ValueError):p.validate_change_set(cs,b,'stop')
    with pytest.raises(ValueError):p.validate_change_set(cs,b,'repoint',target)


def test_actual_repoint_accepts_only_reviewed_dynamic_service_name_dependencies():
    review = EV / 'scenario-c-revalidation-20261015T1740Z'
    source = p.load(review / 'live-template.json')['TemplateBody']
    target = p.load(review / 'repoint-generated/repoint-stopped.template.json')
    cs = p.load(review / 'change-set-final.json')
    assert p.validate_change_set(cs, source, 'repoint', target)
    tampered = copy.deepcopy(cs)
    alarm = next(x['ResourceChange'] for x in tampered['Changes']
                 if x['ResourceChange']['LogicalResourceId'] == 'AlarmasCriticasAlarmaSaturacionCpu3C8591DA')
    alarm['Details'][0]['CausingEntity'] = 'DatabasePostgres277EF4CB.Endpoint.Address'
    with pytest.raises(ValueError): p.validate_change_set(tampered, source, 'repoint', target)
    tampered = copy.deepcopy(cs)
    tampered['Changes'].append(copy.deepcopy(tampered['Changes'][0]))
    with pytest.raises(ValueError): p.validate_change_set(tampered, source, 'repoint', target)


@pytest.mark.parametrize('case', ['static', 'cause', 'property', 'scope', 'replacement', 'extra',
                                 'duplicate', 'missing', 'service-command', 'alarm-template', 'image-template'])
def test_dynamic_dependency_exception_rejects_expanded_scope(case):
    b=baseline();target=p.stopped_template(b);cs=actual_containment_change_set()
    alarm=next(x['ResourceChange'] for x in cs['Changes'] if x['ResourceChange']['ResourceType']=='AWS::CloudWatch::Alarm')
    service=next(x['ResourceChange'] for x in cs['Changes'] if x['ResourceChange']['ResourceType']=='AWS::ECS::Service')
    if case=='static':alarm['Details'][0]['Evaluation']='Static'
    elif case=='cause':alarm['Details'][0]['CausingEntity']='DatabasePostgres277EF4CB.Endpoint.Address'
    elif case=='property':alarm['Details'][0]['Target']['Name']='Threshold'
    elif case=='scope':alarm['Scope'].append('Tags')
    elif case=='replacement':alarm['Replacement']='True'
    elif case=='extra':cs['Changes'].append({'ResourceChange':{'LogicalResourceId':'Unexpected','ResourceType':'AWS::RDS::DBInstance'}})
    elif case=='duplicate':cs['Changes'].append(copy.deepcopy(cs['Changes'][0]))
    elif case=='missing':cs['Changes'].remove(next(x for x in cs['Changes'] if x['ResourceChange']['LogicalResourceId']==alarm['LogicalResourceId']))
    elif case=='service-command':service['Details'][0]['Target']['Name']='TaskDefinition'
    elif case=='alarm-template':target['Resources'][alarm['LogicalResourceId']]['Properties']['Threshold']=1
    elif case=='image-template':p.task_names(target)['backend'][1]['Image']='unexpected'
    with pytest.raises(ValueError):p.validate_change_set(cs,b,'stop',target)


def test_local_generation_and_future_bindings_never_call_network(tmp_path, monkeypatch):
    import socket
    def forbidden(*a, **kw):raise AssertionError('Network not authorized')
    monkeypatch.setattr(socket, 'socket', forbidden)
    initial=tmp_path/'initial'
    monkeypatch.setattr(sys,'argv',['prepare','--evidence-root',str(EV),'--output',str(initial)])
    assert p.main()==0
    plan=p.load(initial/'plan-c.json');assert plan['executionAuthorized'] is False and plan['restoreEndpoint'] is None
    assert not (initial/'register-c-incompatibility.json').exists()
    assert not (initial/'lock-c.json').exists()
    assert p.load(initial/'lock-requirements.json')['existingCLockMustNotBeReplaced'] is True
    assert p.load(initial/'inventory-definition-requirements.json')['executionAuthorized'] is False
    output_receipt = tmp_path/'stack-outputs.json'
    output_receipt.write_text(json.dumps({'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
        'stack': {'StackName': 'SagrilaftStack-' + p.LAB, 'StackStatus': 'UPDATE_COMPLETE'},
        'outputs': {'P20CInventoryTaskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-task',
                    'P20CInventoryExecutionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-execution',
                    'P20CInventoryDbSecretArn': f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/c_inventory_db_credentials-AbCd1234'}}))
    inventory=tmp_path/'inventory'
    monkeypatch.setattr(sys,'argv',['prepare','--evidence-root',str(EV),'--output',str(inventory),
        '--prepared',str(initial),'--prepare-inventory-definition',str(output_receipt)])
    assert p.main()==0
    inventory_task=p.load(inventory/'register-c-inventory.json')
    assert inventory_task['taskRoleArn'].endswith('-c-inventory-task')
    assert inventory_task['containerDefinitions'][0]['command']==['P20_C_INVENTORY']
    assert p.load(inventory/'binding.json')['executionAuthorized'] is False
    stack_receipt = tmp_path/'stack-provisioner-outputs.json'
    prefix = f'arn:aws:secretsmanager:us-east-1:{p.ACCOUNT}:secret:sagrilaft/{p.LAB}/'
    stack_receipt.write_text(json.dumps({'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
        'stack': {'StackName': 'SagrilaftStack-' + p.LAB, 'StackStatus': 'UPDATE_COMPLETE'},
        'outputs': {'DbSecretArn': prefix + 'db_credentials-AbCd1234',
                    'P20CInventoryDbSecretArn': prefix + 'c_inventory_db_credentials-XyZ9876',
                    'P20CInventoryProvisionTaskRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-provision-task',
                    'P20CInventoryProvisionExecutionRoleArn': f'arn:aws:iam::{p.ACCOUNT}:role/sagrilaft-{p.LAB}-c-inventory-provision-execution'}}))
    database_receipt = tmp_path/'clone-readonly.json'
    database_receipt.write_text(json.dumps({'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
        'database': {'DBInstanceIdentifier': p.WORK, 'DBInstanceStatus': 'available',
                     'StorageEncrypted': True, 'PubliclyAccessible': False,
                     'Endpoint': {'Address': p.HOST}, 'DBSubnetGroup': {'VpcId': p.VPC},
                     'VpcSecurityGroups': [{'VpcSecurityGroupId': p.SG}]}}))
    provisioner = tmp_path/'provisioner'
    monkeypatch.setattr(sys, 'argv', ['prepare', '--evidence-root', str(EV), '--output', str(provisioner),
        '--prepared', str(initial), '--prepare-inventory-provisioner-definition', str(stack_receipt),
        '--database-receipt', str(database_receipt)])
    assert p.main() == 0
    request = p.load(provisioner/'register-c-inventory-provisioner.json')
    assert p.validate_inventory_provisioner_request(request)
    binding = p.load(provisioner/'binding.json')
    assert binding['executionAuthorized'] is False and binding['databaseCredentialsTested'] is False
    r=receipt();r['lockBody']={'runId':plan['runId'],'planHash':plan['planHash']}
    fpath=tmp_path/'receipt.json';fpath.write_text(json.dumps(r))
    bound=tmp_path/'bound'
    monkeypatch.setattr(sys,'argv',['prepare','--evidence-root',str(EV),'--output',str(bound),'--prepared',str(initial),'--bind-ddl-receipt',str(fpath)])
    assert p.main()==0 and (bound/'register-c-incompatibility.json').exists()
    r['controls']['incompatible']=True
    restore={'restoreRequest':p.load(initial/'restore-snapshot.json'),'database':restored_db(), 'containment':r,
             'snapshot':r['snapshot'],'snapshotControls':controls(),'restoredControls':controls()}
    endpoint_receipt={k:v for k,v in restore.items() if k != 'restoredControls'}
    fpath.write_text(json.dumps(endpoint_receipt));query=tmp_path/'query-only'
    monkeypatch.setattr(sys,'argv',['prepare','--evidence-root',str(EV),'--output',str(query),'--prepared',str(initial),'--bind-restore-endpoint',str(fpath)])
    assert p.main()==0 and (query/'register-c-verify-restored.json').exists()
    assert not (query/'repoint-stopped.template.json').exists()
    assert not (query/'register-c-backend-restored.json').exists()
    fpath.write_text(json.dumps(restore));after=tmp_path/'restored'
    live_template = p.load(EV / 'scenario-c-current-inventory-20261014T2259Z/live-template.json')['TemplateBody']
    live_receipt = {'checkedAtUTC': datetime.now(timezone.utc).isoformat(),
        'identity': {'Account': p.ACCOUNT}, 'region': 'us-east-1',
        'stack': {'StackName': 'SagrilaftStack-' + p.LAB, 'StackStatus': 'UPDATE_COMPLETE'},
        'template': live_template, 'lockHead': {'ETag': 'same'}, 'expectedLockETag': 'same',
        'lockBody': {'runId': plan['runId'], 'planHash': plan['planHash']},
        'running': {'taskArns': []}, 'pending': {'taskArns': []},
        'services': {'services': [{'desiredCount': 0, 'runningCount': 0, 'pendingCount': 0} for _ in range(4)]}}
    live_path = tmp_path/'live-template-receipt.json';live_path.write_text(json.dumps(live_receipt))
    monkeypatch.setattr(sys,'argv',['prepare','--evidence-root',str(EV),'--output',str(after),'--prepared',str(initial),
        '--bind-restore-receipt',str(fpath),'--live-template-receipt',str(live_path)])
    assert p.main()==0
    smoke=(after/'smoke-restored.py').read_text()
    assert "OLD_CITY='P20 prueba de recuperación B'" in smoke and "\nCITY='P20 prueba de recuperación C'" in smoke
    assert "HOST='"+p.RESTORE+'.verified.us-east-1.rds.amazonaws.com' in smoke
    assert "P20_C_ALLOW_SYNTHETIC_WRITE" in smoke
    assert p.load(after/'binding.json')['executionAuthorized'] is False


def test_endpoint_binding_cannot_authorize_repoint_without_sql_controls():
    r=receipt();r['controls']['incompatible']=True
    plan={'runId':'run-c','planHash':'plan-c','serviceNames':[s['serviceName'] for s in r['services']['services']],
          'stoppedTemplateSha256':p.fingerprint(p.stopped_template(baseline()))}
    request={'DBSnapshotIdentifier':p.SNAPSHOT,'DBInstanceIdentifier':p.RESTORE}
    actual={'restoreRequest':request,'database':restored_db(),'snapshot':r['snapshot'],
            'snapshotControls':controls(),'containment':r}
    assert p.validate_restore_receipt(actual,request,plan,require_controls=False).startswith(p.RESTORE)
    with pytest.raises(KeyError):p.validate_restore_receipt(actual,request,plan)
    actual['database']['PubliclyAccessible']=True
    with pytest.raises(ValueError):p.validate_restore_receipt(actual,request,plan,require_controls=False)
