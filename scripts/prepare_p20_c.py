#!/usr/bin/env python3
"""P20 C local artifact preparation and receipt validation. No AWS/network runner."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/evidencia/p20-recuperacion/9c67b6ea6842'
LAB = 'p20-9c67b6ea6842'
ACCOUNT = '874641912777'
WORK = LAB + '-c7-test-20261012'
HOST = WORK + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
RESTORE = LAB + '-restore-c-20261014'
SNAPSHOT = LAB + '-c-pre-incompatible-20261014'
DIGEST = 'sha256:8550752868887cd634844a65cb0f16d1604817e6fb5a8e50ba560597771dce00'
VPC = 'vpc-05af839e659c00896'
SG = 'sg-0f459a29707d769e8'
KMS = 'arn:aws:kms:us-east-1:874641912777:key/e6a377c7-3f0c-46df-8cb2-f391926ec410'
LEGACY_PREPARER_SHA256 = '4bcf42d1d3d5d65af9d6805c8bd0a63bfec47c51e0a4e6eab5a956083f0d7156'
BACKEND_BOOT = '''import os,tempfile,re
from pathlib import Path
from sqlalchemy import URL,create_engine,text,pool
h=__HOST__
assert os.environ.get('DATABASE_HOST')==h and os.environ.get('DATABASE_NAME')=='sagrilaft'
assert os.environ.get('P20_RUN_ID')=='p20-9c67b6ea6842' and os.environ.get('ZOHO_SIGN_ENABLED')=='false'
assert os.environ.get('RUN_MODE')=='server'
assert os.environ.get('APP_ENV')=='staging' and os.environ.get('STORAGE_BACKEND')=='s3' and os.environ.get('S3_BUCKET')
d=tempfile.mkdtemp(prefix='p20-c-tls-');c=Path(d)/'ca.pem';c.write_text(__CA__)
os.environ['DATABASE_URL']=URL.create('postgresql+psycopg',username=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],host=h,port=5432,database='sagrilaft',query={'sslmode':'verify-full','sslrootcert':str(c)}).render_as_string(hide_password=False)
e=create_engine(os.environ['DATABASE_URL'],poolclass=pool.NullPool,connect_args={'connect_timeout':10})
with e.connect() as connection:
 assert connection.execute(text('SELECT current_database()')).scalar_one()=='sagrilaft'
 assert connection.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar_one() is True
e.dispose()
os.execvp('uvicorn',['uvicorn','main:app','--host','0.0.0.0','--port','8000','--workers','1'])
'''


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def environment(container):
    items = container.get('Environment', container.get('environment', []))
    upper = 'Environment' in container
    key, val = ('Name', 'Value') if upper else ('name', 'value')
    require(len({e[key] for e in items}) == len(items), 'Duplicate environment names')
    return {e[key]: e[val] for e in items}


def task_names(template):
    result = {}
    for logical, resource in template['Resources'].items():
        if resource['Type'] == 'AWS::ECS::TaskDefinition':
            c = resource['Properties']['ContainerDefinitions']
            require(len(c) == 1 and c[0]['Name'] not in result, 'Ambiguous task definition')
            result[c[0]['Name']] = (logical, c[0])
    require(set(result) == {'backend', 'frontend', 'portal', 'keycloak', 'migration'}, 'Expected five baseline definitions')
    return result


def validate_hosts(template, host):
    tasks = task_names(template)
    for name, keys in {'backend': ['DATABASE_HOST', 'KEYCLOAK_DB_URL'],
                       'migration': ['DATABASE_HOST', 'KEYCLOAK_DB_URL'], 'keycloak': ['KC_DB_URL']}.items():
        env = environment(tasks[name][1])
        require('DATABASE_URL' not in env, 'Unexpected URL overrides the approved host')
        for key in keys:
            require(env.get(key) == (host if key == 'DATABASE_HOST' else f'jdbc:postgresql://{host}:5432/sagrilaft'), 'Connection outside approved target')
    require(template['Outputs']['EcsDatabaseHost']['Value'] == host, 'Wrong output host')
    env = environment(tasks['backend'][1])
    require(env.get('ZOHO_SIGN_ENABLED') == 'false' and env.get('P20_RUN_ID') == LAB
            and env.get('RUN_MODE') == 'server', 'Wrong backend runtime/Zoho scope')


def stopped_template(baseline):
    validate_hosts(baseline, HOST)
    target = copy.deepcopy(baseline)
    count = 0
    for r in target['Resources'].values():
        if r['Type'] == 'AWS::ECS::Service':
            require(r['Properties']['DesiredCount'] == 1, 'Expected healthy baseline at one')
            r['Properties']['DesiredCount'] = 0
            count += 1
    require(count == 4 and baseline['Outputs']['EcsDesiredCount']['Value'] == '1', 'Expected four services')
    target['Outputs']['EcsDesiredCount']['Value'] = '0'
    restored = copy.deepcopy(target)
    for r in restored['Resources'].values():
        if r['Type'] == 'AWS::ECS::Service':
            r['Properties']['DesiredCount'] = 1
    restored['Outputs']['EcsDesiredCount']['Value'] = '1'
    require(restored == baseline, 'Containment changed other resources')
    return target


def restored_host(db):
    require(db['DBInstanceIdentifier'] == RESTORE, 'Wrong restored identifier')
    h = db['Endpoint']['Address']
    require(bool(re.fullmatch(re.escape(RESTORE) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', h)), 'Unverified restore endpoint')
    require(db['DBInstanceStatus'] == 'available' and db.get('StorageOperationStatus') not in ('Initializing', 'initializing')
            and db.get('StorageInitializationProgress', 100) == 100, 'Restore not ready')
    require(db['StorageEncrypted'] and db['KmsKeyId'] == KMS and not db['PubliclyAccessible']
            and db['DBSubnetGroup']['VpcId'] == VPC and {g['VpcSecurityGroupId'] for g in db['VpcSecurityGroups']} == {SG}, 'Wrong restore network/encryption')
    require(db['Engine'] == 'postgres' and db['EngineVersion'] == '16.13'
            and db['DBInstanceClass'] == 'db.t3.medium' and db['AllocatedStorage'] == 100
            and db['StorageType'] == 'gp2' and db['BackupRetentionPeriod'] == 1
            and not db['MultiAZ'], 'Restore settings differ')
    tags = {t['Key']: t['Value'] for t in db.get('TagList', [])}
    require(tags.get('Project') == 'sagrilaft' and tags.get('Environment') == LAB, 'Missing restore tags')
    return h


def repoint_template(stopped, host):
    require(bool(re.fullmatch(re.escape(RESTORE) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Wrong restored host')
    validate_hosts(stopped, HOST)
    require(all(r['Properties']['DesiredCount'] == 0 for r in stopped['Resources'].values() if r['Type'] == 'AWS::ECS::Service'), 'Services must stay off')
    target = copy.deepcopy(stopped)
    for name in ('backend', 'keycloak', 'migration'):
        c = task_names(target)[name][1]
        for e in c['Environment']:
            if e['Name'] == 'DATABASE_HOST':
                e['Value'] = host
            elif e['Name'] in ('KC_DB_URL', 'KEYCLOAK_DB_URL'):
                e['Value'] = f'jdbc:postgresql://{host}:5432/sagrilaft'
    target['Outputs']['EcsDatabaseHost']['Value'] = host
    validate_hosts(target, host)
    # Reverse only approved host fields, then compare every resource/output.
    reverse = copy.deepcopy(target)
    for name in ('backend', 'keycloak', 'migration'):
        for e in task_names(reverse)[name][1]['Environment']:
            if e['Name'] == 'DATABASE_HOST': e['Value'] = HOST
            elif e['Name'] in ('KC_DB_URL', 'KEYCLOAK_DB_URL'): e['Value'] = f'jdbc:postgresql://{HOST}:5432/sagrilaft'
    reverse['Outputs']['EcsDatabaseHost']['Value'] = HOST
    require(reverse == stopped, 'Repoint changed images, capacity, secrets or unrelated resources')
    return target


def repoint_template_from_live(live, host):
    """Repoint a fresh live P20 template while preserving every current resource."""
    require(bool(re.fullmatch(re.escape(RESTORE) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Wrong restored host')
    require(len(live.get('Resources', {})) >= 157, 'Live C template is unexpectedly incomplete')
    original_ids = set(live['Resources'])
    require({'EcsFargateCInventoryExecutionRole09026C67',
             'EcsFargateCInventoryExecutionRoleDefaultPolicy7052D817',
             'EcsFargateCInventoryProvisionExecutionRole4E61E8AF',
             'EcsFargateCInventoryProvisionExecutionRoleDefaultPolicyD762F55C',
             'EcsFargateCInventoryProvisionTaskRole035A753E',
             'EcsFargateCInventoryTaskRole66BF5F2C',
             'SecretsCInventoryDbSecret1F34AF4E'} <= original_ids,
            'Current C inventory/provisioning resources are missing from live template')
    validate_hosts(live, HOST)
    services = [r for r in live['Resources'].values() if r['Type'] == 'AWS::ECS::Service']
    require(len(services) == 4 and all(r['Properties']['DesiredCount'] == 0 for r in services),
            'All four ECS services must already be stopped')
    require(live['Outputs']['EcsDesiredCount']['Value'] == '0', 'ECS desired-count output must remain zero')
    target = copy.deepcopy(live)
    for name in ('backend', 'keycloak', 'migration'):
        c = task_names(target)[name][1]
        for item in c['Environment']:
            if item['Name'] == 'DATABASE_HOST':
                item['Value'] = host
            elif item['Name'] in ('KC_DB_URL', 'KEYCLOAK_DB_URL'):
                item['Value'] = f'jdbc:postgresql://{host}:5432/sagrilaft'
    target['Outputs']['EcsDatabaseHost']['Value'] = host
    validate_hosts(target, host)
    require(set(target['Resources']) == original_ids, 'Repoint added or removed resources')
    reverse = copy.deepcopy(target)
    for name in ('backend', 'keycloak', 'migration'):
        for item in task_names(reverse)[name][1]['Environment']:
            if item['Name'] == 'DATABASE_HOST':
                item['Value'] = HOST
            elif item['Name'] in ('KC_DB_URL', 'KEYCLOAK_DB_URL'):
                item['Value'] = f'jdbc:postgresql://{HOST}:5432/sagrilaft'
    reverse['Outputs']['EcsDatabaseHost']['Value'] = HOST
    require(reverse == live, 'Repoint changed resources, images, capacity, secrets, roles, or unrelated outputs')
    return target


def validate_live_repoint_receipt(receipt, plan):
    checked = datetime.fromisoformat(receipt['checkedAtUTC'])
    age = (datetime.now(timezone.utc) - checked).total_seconds()
    require(0 <= age <= 300, 'Live template receipt expired or from future')
    require(receipt.get('identity', {}).get('Account') == ACCOUNT and receipt.get('region') == 'us-east-1',
            'Wrong account/region for live template receipt')
    require(receipt.get('stack', {}).get('StackName') == 'SagrilaftStack-' + LAB
            and receipt['stack'].get('StackStatus') == 'UPDATE_COMPLETE', 'Stack not stable for repoint')
    require(receipt.get('lockBody') == {'runId': plan['runId'], 'planHash': plan['planHash']}
            and receipt.get('lockHead', {}).get('ETag') == receipt.get('expectedLockETag'),
            'C lock ownership/ETag differs from the existing attempt')
    require(not receipt.get('running', {}).get('taskArns') and not receipt.get('pending', {}).get('taskArns'),
            'ECS tasks are still active')
    services = receipt.get('services', {}).get('services', [])
    require(len(services) == 4 and all([s['desiredCount'], s['runningCount'], s['pendingCount']] == [0, 0, 0]
            for s in services), 'Four ECS services must remain at zero')
    template = receipt.get('template')
    require(isinstance(template, dict) and template.get('Resources') and template.get('Outputs'),
            'Full live TemplateBody is required')
    return template


def validate_repoint_receipt(receipt, plan):
    template = validate_live_repoint_receipt(receipt, plan)
    db = receipt.get('restoredDatabase', {})
    host = restored_host(db)
    snapshot = receipt.get('sourceSnapshot', {})
    require(snapshot.get('DBSnapshotIdentifier') == SNAPSHOT and snapshot.get('Status') == 'available'
            and snapshot.get('Encrypted') is True and snapshot.get('KmsKeyId') == KMS
            and snapshot.get('Engine') == 'postgres' and snapshot.get('EngineVersion') == '16.13',
            'C source snapshot is not verified/available')
    tags = {t.get('Key'): t.get('Value') for t in receipt.get('sourceSnapshotTags', [])}
    require(tags.get('Project') == 'sagrilaft' and tags.get('Environment') == LAB and tags.get('Scenario') == 'C',
            'C source snapshot tags differ')
    controls = receipt.get('restoredControls', {})
    validate_controls(controls)
    require(controls.get('incompatible') is False, 'Restored controls are not compatible')
    require(host == db['Endpoint']['Address'], 'Restored host did not come from the described RDS endpoint')
    return template, host


def validate_controls(controls):
    require(controls.get('mainRevision') == 'c7a1c1a65662' and controls.get('bRevision') == 'p20b_expand_01'
            and controls.get('formId') == '73bf8b16-9551-4656-965d-518afc19d7d1'
            and controls.get('city') == 'P20 prueba de recuperación B' and controls.get('state') == 'borrador'
            and controls.get('incompatible') is False and bool(controls.get('tableCounts')), 'Wrong compatible control')


def validate_containment(receipt, run_id, plan_hash, expected_names, template_hash, now=None, incompatible=False):
    now = now or datetime.now(timezone.utc)
    age = (now - datetime.fromisoformat(receipt['checkedAtUTC'])).total_seconds()
    require(0 <= age <= 300, 'Receipt expired or from future; fresh authorized read required')
    require(receipt['identity']['Account'] == ACCOUNT and receipt['region'] == 'us-east-1', 'Wrong account/region')
    require(receipt['stack']['StackName'] == 'SagrilaftStack-' + LAB and receipt['stack']['StackStatus'] in ('UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'), 'Stack not terminal')
    require(fingerprint(receipt['template']) == template_hash, 'Live containment template differs')
    services = receipt['services']['services']
    require(not receipt['services'].get('failures') and len(services) == 4
            and len({s['serviceName'] for s in services}) == 4, 'Four distinct services required')
    require({s['serviceName'] for s in services} == set(expected_names), 'Wrong service identities')
    for s in services:
        require(s['serviceName'].startswith('SagrilaftStack-' + LAB + '-EcsFargate')
                and s['clusterArn'].endswith(':cluster/sagrilaft-' + LAB)
                and [s[k] for k in ('desiredCount', 'runningCount', 'pendingCount')] == [0, 0, 0], 'Services not contained')
    require(not receipt['running']['taskArns'] and not receipt['pending']['taskArns']
            and not receipt['activeOwnerProcesses'] and not receipt['activeOperations'], 'Task/operator/operation still active')
    require(receipt['lockHead']['ETag'] == receipt['expectedLockETag']
            and receipt['lockBody'] == {'runId': run_id, 'planHash': plan_hash}, 'Lock ownership changed')
    db = receipt['database']
    require(db['DBInstanceIdentifier'] == WORK and db['Endpoint']['Address'] == HOST
            and db['DBInstanceStatus'] == 'available' and db['StorageEncrypted'] and db['KmsKeyId'] == KMS
            and not db['PubliclyAccessible'] and db['DBSubnetGroup']['VpcId'] == VPC
            and {g['VpcSecurityGroupId'] for g in db['VpcSecurityGroups']} == {SG}, 'Wrong working clone')
    snap = receipt['snapshot']
    require(snap['DBSnapshotIdentifier'] == SNAPSHOT and snap['DBInstanceIdentifier'] == WORK
            and snap['Status'] == 'available' and snap['Encrypted'] and snap['KmsKeyId'] == KMS
            and snap['VpcId'] == VPC and snap['Engine'] == 'postgres' and snap['EngineVersion'] == '16.13', 'Wrong backup/source/state')
    require(datetime.fromisoformat(snap['SnapshotCreateTime']) >= datetime.fromisoformat(receipt['quiescedAtUTC']), 'Backup predates containment')
    tags = {t['Key']: t['Value'] for t in receipt['snapshotTags']}
    require(tags.get('Project') == 'sagrilaft' and tags.get('Environment') == LAB, 'Snapshot outside C lab')
    require(receipt['controls']['incompatible'] is incompatible, 'Wrong phase of working schema')
    validate_controls({**receipt['controls'], 'incompatible': False})
    return fingerprint(receipt)


def validate_restore_receipt(receipt, restore_request, plan, require_controls=True):
    require(receipt['restoreRequest'] == restore_request, 'Restore source/input differs')
    h = restored_host(receipt['database'])
    validate_controls(receipt['snapshotControls'])
    if require_controls:
        validate_controls(receipt['restoredControls'])
        require(receipt['restoredControls'] == receipt['snapshotControls'], 'Restored controls/counts differ')
    require(receipt['snapshot']['DBSnapshotIdentifier'] == SNAPSHOT and receipt['snapshot']['DBInstanceIdentifier'] == WORK
            and receipt['snapshot']['Status'] == 'available' and receipt['snapshot']['Encrypted']
            and receipt['snapshot']['KmsKeyId'] == KMS, 'Restore backup lineage differs')
    # Revalidate containment and current lock; source snapshot remains the pre-fault one.
    validate_containment(receipt['containment'], plan['runId'], plan['planHash'],
                         plan['serviceNames'], plan['stoppedTemplateSha256'], incompatible=True)
    return h


def command(source):
    data = base64.b64encode(zlib.compress(source.encode())).decode()
    result = ['python', '-c', "import base64,zlib;exec(compile(zlib.decompress(base64.b64decode(" + repr(data) + ")),'p20_c_inline','exec'))"]
    require(len(json.dumps({'containerOverrides': [{'name': 'backend', 'command': result}]}).encode()) < 8192, 'Command too large')
    return result


def direct_python_task_command(source):
    """Build arguments for a TD whose ENTRYPOINT is explicitly Python.

    ECS RunTask can override a container command, but cannot override its
    image ENTRYPOINT. The backend image's default ENTRYPOINT is
    ``sh entrypoint.sh``; therefore fixture tasks must pin ENTRYPOINT to
    Python in the task definition and pass only Python arguments here.
    """
    full = command(source)
    require(full[0:2] == ['python', '-c'], 'Unexpected inline Python command')
    return full[1:]


def guarded_fixture_entrypoint(source, ca, args, sentinel, include_sentinel=False):
    """Pin fixture code in ENTRYPOINT; RunTask command overrides can only pass args."""
    require(sentinel in {'P20_C_INVENTORY', 'P20_C_PROVISION_INVENTORY', 'P20_C_QUERY', 'P20_C_DDL'}, 'Unknown fixed command sentinel')
    source_b64 = base64.b64encode(zlib.compress(source.encode())).decode()
    fixture_argv = ['p20_c_fixture', *([sentinel] if include_sentinel else []), *args]
    guard = (
        'import sys; '
        f'expected={sentinel!r}; '
        'sys.argv[1:] == [expected] or sys.exit("P20-C rejected command override"); '
        'import base64,zlib; from pathlib import Path; '
        f'Path("/tmp/p20-c-ca.pem").write_text({ca!r}); '
        f'sys.argv={fixture_argv!r}; '
        f'exec(compile(zlib.decompress(base64.b64decode({source_b64!r})),"p20_c_fixed_fixture","exec"))'
    )
    require(len(guard.encode()) < 8192, 'Pinned inventory entrypoint exceeds ECS command limit')
    return ['/usr/local/bin/python', '-c', guard]


def definition(base, host, ca, kind, fixture_source=None, action=None, receipt_hash=None,
              inventory_security=None, provision_security=None):
    require(host == HOST or bool(re.fullmatch(re.escape(RESTORE) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Bad task target')
    require(not base['containerDefinitions'][0].get('entryPoint'), 'Image/task entrypoint must be empty')
    result = {k: copy.deepcopy(base[k]) for k in ('taskRoleArn', 'executionRoleArn', 'networkMode', 'requiresCompatibilities', 'cpu', 'memory', 'runtimePlatform') if k in base}
    if kind not in ('inventory', 'inventory-provisioner'):
        require(all(result[k].startswith('arn:aws:iam::' + ACCOUNT + ':role/SagrilaftStack-p20-')
                    for k in ('taskRoleArn', 'executionRoleArn')), 'Roles outside P20')
    result['family'] = 'sagrilaft-' + LAB + '-c-' + kind
    c = copy.deepcopy(base['containerDefinitions'][0]);require(c['name'] == 'backend', 'Backend source required')
    c['image'] = ACCOUNT + '.dkr.ecr.us-east-1.amazonaws.com/sagrilaft-' + LAB + '-backend@' + DIGEST
    # Override the image's default ``sh entrypoint.sh`` so this task executes
    # the reviewed Python fixture directly. An empty ENTRYPOINT would inherit
    # the Dockerfile default and start the app/server instead.
    c['entryPoint'] = ['python'];c['portMappings'] = []
    for e in c['environment']:
        if e['name'] == 'DATABASE_HOST': e['value'] = host
        elif e['name'] == 'KEYCLOAK_DB_URL': e['value'] = f'jdbc:postgresql://{host}:5432/sagrilaft'
        elif e['name'] == 'RUN_MODE': e['value'] = 'p20-c-fixture' if fixture_source else 'server'
    env = environment(c);require('DATABASE_URL' not in env and env.get('ZOHO_SIGN_ENABLED') == 'false' and env.get('P20_RUN_ID') == LAB, 'Unexpected task env')
    if fixture_source:
        c.pop('healthCheck', None)
        ident = WORK if host == HOST else RESTORE
        args = [action, '--db-identifier', ident, '--expected-host', host, '--ssl-root-cert', '/tmp/p20-c-ca.pem']
        if action == 'incompatibility':
            require(receipt_hash, 'DDL artifacts require validated fresh receipt')
            args += ['--apply', '--guard-receipt-sha256', receipt_hash]
            c['environment'].append({'name': 'P20_C_GUARD_SHA256', 'value': receipt_hash})
        else: args.append('--query')
        if kind == 'inventory':
            require(action == 'inventory', 'Dedicated inventory task only accepts the inventory action')
            require(inventory_security is not None, 'Inventory requires dedicated read-only roles and secret ARN')
            task_role = inventory_security.get('taskRoleArn', '')
            execution_role = inventory_security.get('executionRoleArn', '')
            secret_arn = inventory_security.get('secretArn', '')
            role_prefix = f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-'
            require(task_role == role_prefix + 'task' and execution_role == role_prefix + 'execution',
                    'Inventory role ARNs must be the dedicated P20-C roles')
            require(bool(re.fullmatch(r'arn:aws:secretsmanager:us-east-1:' + ACCOUNT +
                                      r':secret:sagrilaft/' + re.escape(LAB) +
                                      r'/c_inventory_db_credentials-[A-Za-z0-9]+', secret_arn)),
                    'Inventory secret must be the dedicated P20-C read-only secret')
            result['taskRoleArn'], result['executionRoleArn'] = task_role, execution_role
            c['secrets'] = [
                {'name': 'DB_USER', 'valueFrom': secret_arn + ':username::'},
                {'name': 'DB_PASSWORD', 'valueFrom': secret_arn + ':password::'},
            ]
            require({s['name'] for s in c['secrets']} == {'DB_USER', 'DB_PASSWORD'}, 'Inventory secret set is not minimal')
            c['environment'] = [
                {'name': 'DATABASE_NAME', 'value': 'sagrilaft'},
                {'name': 'DATABASE_HOST', 'value': host},
                {'name': 'P20_RUN_ID', 'value': LAB},
                {'name': 'RUN_MODE', 'value': 'p20-c-fixture'},
                {'name': 'ZOHO_SIGN_ENABLED', 'value': 'false'},
            ]
            sentinel = 'P20_C_INVENTORY'
            c['entryPoint'] = guarded_fixture_entrypoint(fixture_source, ca, args, sentinel)
            c['command'] = [sentinel]
        elif kind == 'inventory-provisioner':
            require(action == 'provision-inventory', 'Provisioner only accepts role creation and grant action')
            require(provision_security is not None, 'Provisioner requires separate least-privilege IAM roles and two P20 secret ARNs')
            task_role = provision_security.get('taskRoleArn', '')
            execution_role = provision_security.get('executionRoleArn', '')
            admin_secret = provision_security.get('adminSecretArn', '')
            inventory_secret = provision_security.get('inventorySecretArn', '')
            role_prefix = f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-provision-'
            require(task_role == role_prefix + 'task' and execution_role == role_prefix + 'execution',
                    'Provisioner role ARNs must be the dedicated P20-C provisioning roles')
            secret_prefix = f'arn:aws:secretsmanager:us-east-1:{ACCOUNT}:secret:sagrilaft/{LAB}/'
            require(bool(re.fullmatch(re.escape(secret_prefix) + r'db_credentials-[A-Za-z0-9]+', admin_secret)),
                    'Provisioner admin secret must be the P20 DB credentials secret')
            require(bool(re.fullmatch(re.escape(secret_prefix) + r'c_inventory_db_credentials-[A-Za-z0-9]+', inventory_secret)),
                    'Provisioner inventory secret must be the dedicated P20-C secret')
            require(admin_secret != inventory_secret, 'Provisioner secrets must be distinct')
            result['taskRoleArn'], result['executionRoleArn'] = task_role, execution_role
            c['secrets'] = [
                {'name': 'DB_ADMIN_USER', 'valueFrom': admin_secret + ':username::'},
                {'name': 'DB_ADMIN_PASSWORD', 'valueFrom': admin_secret + ':password::'},
                {'name': 'INVENTORY_DB_USER', 'valueFrom': inventory_secret + ':username::'},
                {'name': 'INVENTORY_DB_PASSWORD', 'valueFrom': inventory_secret + ':password::'},
            ]
            c['environment'] = [
                {'name': 'DATABASE_NAME', 'value': 'sagrilaft'},
                {'name': 'DATABASE_HOST', 'value': host},
                {'name': 'EXPECTED_DB_IDENTIFIER', 'value': WORK},
                {'name': 'EXPECTED_DB_ADMIN_USER', 'value': 'sagrilaft_user'},
                {'name': 'P20_RUN_ID', 'value': LAB},
                {'name': 'RUN_MODE', 'value': 'p20-c-provisioner'},
                {'name': 'ZOHO_SIGN_ENABLED', 'value': 'false'},
            ]
            args = ['--expected-db-identifier', WORK, '--expected-host', host,
                    '--ssl-root-cert', '/tmp/p20-c-ca.pem']
            sentinel = 'P20_C_PROVISION_INVENTORY'
            c['entryPoint'] = guarded_fixture_entrypoint(fixture_source, ca, args, sentinel,
                                                        include_sentinel=True)
            c['command'] = [sentinel]
        else:
            boot = 'import sys\nfrom pathlib import Path\nPath("/tmp/p20-c-ca.pem").write_text(' + repr(ca) + ')\nsys.argv=["p20_c_fixture",*' + repr(args) + ']\n' + fixture_source
            c['entryPoint'] = guarded_fixture_entrypoint(fixture_source, ca, args, 'P20_C_DDL' if action == 'incompatibility' else 'P20_C_QUERY')
            c['command'] = ['P20_C_DDL' if action == 'incompatibility' else 'P20_C_QUERY']
            c['secrets'] = [s for s in c['secrets'] if s['name'] in ('DB_USER', 'DB_PASSWORD')]
            require({s['name'] for s in c['secrets']} == {'DB_USER', 'DB_PASSWORD'}, 'Missing DB secrets')
    else:
        c['command'] = direct_python_task_command(BACKEND_BOOT.replace('__HOST__', repr(host)).replace('__CA__', repr(ca)))
    prefixes = ('arn:aws:secretsmanager:us-east-1:' + ACCOUNT + ':secret:sagrilaft/' + LAB + '/',
                'arn:aws:ssm:us-east-1:' + ACCOUNT + ':parameter/sagrilaft/' + LAB + '/')
    require(all(s['valueFrom'].startswith(prefixes) for s in c['secrets']), 'Shared credentials refused')
    result['containerDefinitions'] = [c]
    result['tags'] = [{'key': 'Project', 'value': 'sagrilaft'}, {'key': 'Environment', 'value': LAB}, {'key': 'Scenario', 'value': 'C'}]
    return result


def validate_inventory_request(requested):
    """Rebuild the approved inventory definition; never trust a caller-supplied command."""
    require(requested.get('family') == 'sagrilaft-' + LAB + '-c-inventory', 'Wrong inventory family')
    c = requested.get('containerDefinitions', [{}])[0]
    secrets = c.get('secrets', [])
    refs = {item.get('name'): item.get('valueFrom', '') for item in secrets}
    user_ref, password_ref = refs.get('DB_USER', ''), refs.get('DB_PASSWORD', '')
    suffix = ':username::'
    require(user_ref.endswith(suffix), 'Inventory username must come from the dedicated secret JSON key')
    secret_arn = user_ref[:-len(suffix)]
    require(password_ref == secret_arn + ':password::', 'Inventory password secret reference differs')
    fixture = (ROOT / 'backend/scripts/p20_c_fixture.py').read_text()
    ca = (EVIDENCE / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    base = load(EVIDENCE / 'scenario-b-functional-smoke-20261014T155828Z/backend-definition.json')['taskDefinition']
    target_env = environment(c)
    target_host = target_env.get('DATABASE_HOST', '')
    require(target_host in (HOST, RESTORE + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'),
            'Inventory target must be the exact approved P20 C clone or restore endpoint')
    expected = definition(base, target_host, ca, 'inventory', fixture, 'inventory', inventory_security={
        'taskRoleArn': f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-task',
        'executionRoleArn': f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-execution',
        'secretArn': secret_arn,
    })
    require(requested == expected, 'Inventory definition differs from the locally rebuilt fixed request')
    return True


def validate_inventory_provisioner_request(requested):
    """Rebuild the fixed one-shot DB-role provisioning task; reject command drift."""
    require(requested.get('family') == 'sagrilaft-' + LAB + '-c-inventory-provisioner',
            'Wrong inventory provisioner family')
    c = requested.get('containerDefinitions', [{}])[0]
    refs = {item.get('name'): item.get('valueFrom', '') for item in c.get('secrets', [])}
    required_names = {'DB_ADMIN_USER', 'DB_ADMIN_PASSWORD', 'INVENTORY_DB_USER', 'INVENTORY_DB_PASSWORD'}
    require(set(refs) == required_names and len(c.get('secrets', [])) == len(required_names),
            'Provisioner must receive exactly four fields from two P20 secrets')
    admin_secret = refs['DB_ADMIN_USER'].removesuffix(':username::')
    inventory_secret = refs['INVENTORY_DB_USER'].removesuffix(':username::')
    require(refs['DB_ADMIN_USER'] == admin_secret + ':username::'
            and refs['DB_ADMIN_PASSWORD'] == admin_secret + ':password::',
            'Admin username/password must use matching JSON keys from one secret')
    require(refs['INVENTORY_DB_USER'] == inventory_secret + ':username::'
            and refs['INVENTORY_DB_PASSWORD'] == inventory_secret + ':password::',
            'Inventory username/password must use matching JSON keys from one secret')
    fixture = (ROOT / 'backend/scripts/p20_c_provision_inventory.py').read_text()
    ca = (EVIDENCE / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
    base = load(EVIDENCE / 'scenario-b-functional-smoke-20261014T155828Z/backend-definition.json')['taskDefinition']
    expected = definition(base, HOST, ca, 'inventory-provisioner', fixture, 'provision-inventory',
                          provision_security={
        'taskRoleArn': f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-provision-task',
        'executionRoleArn': f'arn:aws:iam::{ACCOUNT}:role/sagrilaft-{LAB}-c-inventory-provision-execution',
        'adminSecretArn': admin_secret, 'inventorySecretArn': inventory_secret,
    })
    require(requested == expected, 'Provisioner task differs from locally rebuilt fixed request')
    return True


def validate_inventory_provisioner_database_receipt(receipt):
    """Accept only a fresh, read-only receipt for the exact encrypted private clone."""
    database = receipt.get('database', {})
    require(receipt.get('identity', {}).get('Account') == ACCOUNT and receipt.get('region') == 'us-east-1'
            and database.get('DBInstanceIdentifier') == WORK
            and database.get('DBInstanceStatus') == 'available'
            and database.get('StorageEncrypted') is True
            and database.get('PubliclyAccessible') is False
            and database.get('Endpoint', {}).get('Address') == HOST
            and database.get('DBSubnetGroup', {}).get('VpcId') == VPC
            and {item.get('VpcSecurityGroupId') for item in database.get('VpcSecurityGroups', [])} == {SG},
            'Fresh RDS receipt does not prove the exact private encrypted P20 clone')


def validate_registered_definition(actual, requested):
    require(requested['family'] in {'sagrilaft-' + LAB + '-c-' + k for k in
            ('inventory', 'inventory-provisioner', 'incompatibility', 'verify-incompatible', 'verify-restored', 'backend-incompatible', 'backend-restored')}, 'Unapproved C family')
    if requested['family'] == 'sagrilaft-' + LAB + '-c-inventory':
        validate_inventory_request(requested)
    elif requested['family'] == 'sagrilaft-' + LAB + '-c-inventory-provisioner':
        validate_inventory_provisioner_request(requested)
    require(actual['status'] == 'ACTIVE' and actual['family'] == requested['family'], 'Wrong registered family/state')
    require(bool(re.fullmatch(r'arn:aws:ecs:us-east-1:874641912777:task-definition/' + re.escape(requested['family']) + r':[1-9][0-9]*', actual['taskDefinitionArn'])), 'Exact task definition ARN required')
    for key in ('taskRoleArn', 'executionRoleArn', 'networkMode', 'requiresCompatibilities', 'cpu', 'memory'):
        require(actual[key] == requested[key], 'Registered definition changed ' + key)
    require(actual.get('runtimePlatform') == requested.get('runtimePlatform'), 'Runtime platform differs')
    require(len(actual['containerDefinitions']) == 1, 'Unexpected containers')
    old, new = requested['containerDefinitions'][0], actual['containerDefinitions'][0]
    require(new['name'] == 'backend' and new['image'] == old['image'] and new['command'] == old['command']
            and new.get('entryPoint') == old.get('entryPoint') and not new.get('portMappings')
            and not new.get('environmentFiles'), 'Unexpected image/command/entrypoint/network injection')
    require(environment(new) == environment(old), 'Registered environment differs')
    for c in (old, new):
        require(len({s['name'] for s in c['secrets']}) == len(c['secrets']), 'Duplicate secret name')
    require({s['name']: s['valueFrom'] for s in old['secrets']} ==
            {s['name']: s['valueFrom'] for s in new['secrets']}, 'Registered secrets differ')
    require(new.get('logConfiguration') == old.get('logConfiguration')
            and new.get('healthCheck') == old.get('healthCheck'), 'Health/log configuration differs')
    for key in old:
        if key not in ('environment', 'secrets'):
            require(new.get(key) == old[key], 'Unexpected container configuration: ' + key)
    for key in set(new) - set(old):
        require(new[key] in (None, [], {}, False, 0), 'Unexpected registered property: ' + key)
    return actual['taskDefinitionArn']


def validate_change_set(change_set, baseline, phase, target=None):
    require(change_set.get('Status') == 'CREATE_COMPLETE' and change_set.get('ExecutionStatus') == 'AVAILABLE'
            and not change_set.get('NextToken'), 'Complete detailed change-set review required')
    require(change_set['StackName'] == 'SagrilaftStack-' + LAB, 'Wrong stack')
    if phase == 'stop':
        expected = {k for k, r in baseline['Resources'].items() if r['Type'] == 'AWS::ECS::Service'}
    else:
        require(phase == 'repoint', 'Unknown change-set phase')
        expected = {task_names(baseline)[name][0] for name in ('backend', 'keycloak', 'migration')}
        expected |= {k for k, r in baseline['Resources'].items() if r['Type'] == 'AWS::ECS::Service'
                     and any(name in k for name in ('BackendService', 'KeycloakService'))}
    changes = [c['ResourceChange'] for c in change_set['Changes']]
    ids = {c['LogicalResourceId'] for c in changes}
    require(len(changes) == len(ids), 'Duplicate change-set resource')
    # CloudFormation reevaluates these exact, unchanged GetAtt(Name) consumers
    # when ECS services/task definitions change. Keep phase-specific allowlists.
    dependent_details = {
        'AlarmasCriticasAlarmaSaturacionCpu3C8591DA': {('Dimensions', 'EcsFargateBackendService10F4F273.Name')},
        'AlarmasCriticasAlarmaSaturacionMemoria42793BCD': {('Dimensions', 'EcsFargateBackendService10F4F273.Name')},
        'DashboardTecnico73BEF476': {('DashboardBody', 'EcsFargateBackendService10F4F273.Name'),
                                   ('DashboardBody', 'EcsFargatePortalService528B1C2E.Name')},
    }
    repoint_dependent_details = {
        'AlarmasCriticasAlarmaSaturacionCpu3C8591DA': {('Dimensions', 'EcsFargateBackendService10F4F273.Name')},
        'AlarmasCriticasAlarmaSaturacionMemoria42793BCD': {('Dimensions', 'EcsFargateBackendService10F4F273.Name')},
        'DashboardTecnico73BEF476': {('DashboardBody', 'EcsFargateBackendService10F4F273.Name')},
    }
    dynamic_ids = ids - expected
    if dynamic_ids:
        allowed_dynamic = dependent_details if phase == 'stop' else repoint_dependent_details
        require(dynamic_ids == set(allowed_dynamic) and expected <= ids,
                'Unexpected dependent resources')
        if phase == 'stop':
            require(target is not None and target == stopped_template(baseline),
                    'Dependent reevaluation requires exact capacity-only target template')
        else:
            require(target is not None and target == repoint_template_from_live(
                baseline, target['Outputs']['EcsDatabaseHost']['Value']),
                'Dependent reevaluation requires exact live-template connection-only repoint')
        for change in changes:
            require(change.get('Scope') == ['Properties'], 'Unexpected change scope')
            details = change.get('Details', [])
            require(bool(details), 'Missing property-level change details')
            if change['LogicalResourceId'] in dynamic_ids:
                observed = []
                for detail in details:
                    prop = detail.get('Target', {})
                    require(prop.get('Attribute') == 'Properties' and prop.get('RequiresRecreation') == 'Never'
                            and detail.get('Evaluation') == 'Dynamic'
                            and detail.get('ChangeSource') == 'ResourceAttribute', 'Dependent change is not a harmless reevaluation')
                    observed.append((prop.get('Name'), detail.get('CausingEntity')))
                require(len(observed) == len(set(observed))
                        and set(observed) == allowed_dynamic[change['LogicalResourceId']], 'Unexpected dependency/property')
            elif phase == 'repoint' and change['ResourceType'] == 'AWS::ECS::Service':
                service = change['LogicalResourceId']
                task = ('EcsFargateBackendTaskDefinition4A090F71' if 'BackendService' in service
                        else 'EcsFargateKeycloakTaskDefinition4D3D6C0E')
                require(len(details) == 1 and details[0].get('Evaluation') == 'Static'
                        and details[0].get('ChangeSource') == 'ResourceReference'
                        and details[0].get('CausingEntity') == task
                        and details[0].get('Target') == {'Attribute': 'Properties', 'Name': 'TaskDefinition',
                                                         'RequiresRecreation': 'Never'},
                        'Service change must only follow its approved task-definition reference')
            elif phase == 'repoint' and change['ResourceType'] == 'AWS::ECS::TaskDefinition':
                require(len(details) == 1 and details[0].get('Evaluation') == 'Static'
                        and details[0].get('ChangeSource') == 'DirectModification'
                        and details[0].get('Target', {}).get('Attribute') == 'Properties'
                        and details[0].get('Target', {}).get('Name') == 'ContainerDefinitions'
                        and details[0].get('Target', {}).get('RequiresRecreation') == 'Always',
                        'Task definition may only change its reviewed container definition')
            else:
                require(len(details) == 1 and details[0].get('Evaluation') == 'Static'
                        and details[0].get('ChangeSource') == 'DirectModification'
                        and details[0].get('Target') == {'Attribute': 'Properties', 'Name': 'DesiredCount',
                                                          'RequiresRecreation': 'Never'}, 'Service changes more than capacity')
    else:
        require(ids == expected, 'Unexpected change-set resources')
    for c in changes:
        require(c['Action'] == 'Modify' and c['ResourceType'] == baseline['Resources'][c['LogicalResourceId']]['Type'], 'Unexpected change action/type')
        require(c['Replacement'] == ('True' if c['ResourceType'] == 'AWS::ECS::TaskDefinition' else 'False'), 'Unexpected replacement')
    return True


def emit(folder, name, value):
    p = folder / name;p.write_text(json.dumps(value, indent=2) + '\n');p.chmod(0o600)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bind-ddl-receipt', type=Path)
    p.add_argument('--bind-restore-receipt', type=Path)
    p.add_argument('--live-template-receipt', type=Path,
                   help='Fresh current AWS receipt used with --bind-restore-receipt to preserve the live stack template')
    p.add_argument('--prepare-live-repoint', type=Path,
                   help='Generate a repoint from a fresh live AWS/RDS/snapshot and restored-SQL receipt')
    p.add_argument('--bind-restore-endpoint', type=Path)
    p.add_argument('--prepared', type=Path)
    p.add_argument('--bind-registration', type=Path)
    p.add_argument('--prepare-inventory-definition', type=Path,
                   help='Generate a local-only inventory task request from a freshly verified P20 output receipt')
    p.add_argument('--prepare-inventory-provisioner-definition', type=Path,
                   help='Generate a local-only, one-shot provisioner request from a fresh P20 stack receipt')
    p.add_argument('--database-receipt', type=Path,
                   help='Fresh read-only AWS receipt proving the exact encrypted, private P20 clone')
    p.add_argument('--requested-definition', type=Path)
    p.add_argument('--validate-change-set', type=Path)
    p.add_argument('--change-set-phase', choices=['stop', 'repoint'])
    p.add_argument('--reviewed-target', type=Path)
    p.add_argument('--reviewed-source', type=Path,
                   help='Current source template for exact live-template change-set review')
    a = p.parse_args()
    try:
        require(sum(bool(value) for value in (a.bind_ddl_receipt, a.bind_restore_receipt,
                    a.bind_restore_endpoint, a.bind_registration, a.prepare_inventory_definition,
                    a.prepare_inventory_provisioner_definition, a.validate_change_set,
                    a.prepare_live_repoint)) <= 1,
                'Choose exactly one preparation phase')
        e = a.evidence_root
        closure = e / 'scenario-b-formal-closure-20261014T165050Z'
        require(load(closure / 'result.json')['scenarioBClosed'] and load(closure / 'lock-release-result.json')['lockAbsentConfirmed'], 'B must be closed')
        raw = load(closure / 'template.json')['TemplateBody'];baseline = json.loads(raw) if isinstance(raw, str) else raw
        outputs = {v['OutputKey']: v['OutputValue'] for v in load(closure / 'stack.json')['Stacks'][0]['Outputs']}
        backend = load(e / 'scenario-b-functional-smoke-20261014T155828Z/backend-definition.json')['taskDefinition']
        db = load(e / 'scenario-b-additive-execution-20261014T144715Z/continuation-20261014T145909Z/clone-before.json')['DBInstances'][0]
        ca = (e / 'scenario-b-local-preparation-20261014T140343Z/rds-rsa2048-root.pem').read_text()
        fixture = (ROOT / 'backend/scripts/p20_c_fixture.py').read_text()
        a.output.mkdir(parents=True, mode=0o700, exist_ok=False)
        stopped = stopped_template(baseline)
        if a.prepare_live_repoint:
            plan = load(a.prepared / 'plan-c.json') if a.prepared else None
            require(plan is not None and fingerprint({k: v for k, v in plan.items() if k != 'planHash'}) == plan['planHash'],
                    'Original C plan integrity check failed')
            require(plan['account'] == ACCOUNT and plan['environment'] == LAB and plan['restoreIdentifier'] == RESTORE
                    and plan['preparerSha256'] == LEGACY_PREPARER_SHA256,
                    'Only the already locked C plan can be refreshed by this path')
            receipt = load(a.prepare_live_repoint)
            live, host = validate_repoint_receipt(receipt, plan)
            target = repoint_template_from_live(live, host)
            emit(a.output, 'repoint-stopped.template.json', target)
            emit(a.output, 'repoint-diff-summary.json', {
                'status': 'LOCAL_DIFF_ONLY', 'executionAuthorized': False,
                'liveResourceCount': len(live['Resources']), 'targetResourceCount': len(target['Resources']),
                'addedResources': sorted(set(target['Resources']) - set(live['Resources'])),
                'removedResources': sorted(set(live['Resources']) - set(target['Resources'])),
                'replacementTaskDefinitions': sorted(task_names(live)[n][0] for n in ('backend', 'keycloak', 'migration')),
                'dependentServices': ['EcsFargateBackendService10F4F273', 'EcsFargateKeycloakServiceD629B160'],
                'allServiceDesiredCounts': sorted({r['Properties']['DesiredCount'] for r in target['Resources'].values() if r['Type'] == 'AWS::ECS::Service'}),
                'outputChanges': ['EcsDatabaseHost'], 'host': host,
                'sourceTemplateSha256': fingerprint(live), 'receiptSha256': fingerprint(receipt),
            })
            emit(a.output, 'binding.json', {'status': 'LIVE_C_TEMPLATE_REPOINT_PREPARED',
                 'executionAuthorized': False, 'runId': plan['runId'], 'planHash': plan['planHash'],
                 'liveResourceCount': len(live['Resources']), 'host': host,
                 'requiresSeparateChangeSetCreationAndExecutionApproval': True})
            return 0
        if a.validate_change_set:
            source = load(a.reviewed_source) if a.reviewed_source else baseline
            validate_change_set(load(a.validate_change_set), source, a.change_set_phase,
                                load(a.reviewed_target) if a.reviewed_target else None)
            emit(a.output, 'review.json', {'status': 'CHANGE_SET_SCOPE_PASS', 'executionAuthorized': False})
            return 0
        if a.bind_registration:
            require(a.prepared and a.requested_definition, 'Prepared plan and reviewed task input required')
            arn = validate_registered_definition(load(a.bind_registration)['taskDefinition'], load(a.requested_definition))
            request = {'cluster': 'sagrilaft-' + LAB, 'taskDefinition': arn, 'launchType': 'FARGATE', 'count': 1,
                       'networkConfiguration': load(a.prepared / 'task-network.json'), 'enableExecuteCommand': False}
            # Token is intentionally supplied once at execution, never stored in a reusable form here.
            emit(a.output, 'run-task.json', request)
            emit(a.output, 'binding.json', {'status': 'REGISTERED_TASK_PINNED_FOR_REVIEW', 'executionAuthorized': False})
            return 0
        if a.prepare_inventory_definition:
            require(a.prepared is not None, 'Original prepared plan required')
            plan = load(a.prepared / 'plan-c.json')
            require(fingerprint({k: v for k, v in plan.items() if k != 'planHash'}) == plan['planHash'], 'Prepared plan hash changed')
            require(plan['account'] == ACCOUNT and plan['workIdentifier'] == WORK
                    and plan['fixtureSha256'] == hashlib.sha256(fixture.encode()).hexdigest()
                    and plan['sourceBackendDefinitionSha256'] == fingerprint(backend)
                    and plan['preparerSha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'Prepared sources/target differ from current local code')
            receipt = load(a.prepare_inventory_definition)
            require(receipt.get('identity', {}).get('Account') == ACCOUNT and receipt.get('region') == 'us-east-1'
                    and receipt.get('stack', {}).get('StackName') == 'SagrilaftStack-' + LAB
                    and receipt.get('stack', {}).get('StackStatus') in {'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'},
                    'Inventory role/secret outputs must come from terminal P20 stack state')
            out = receipt.get('outputs', {})
            security = {'taskRoleArn': out.get('P20CInventoryTaskRoleArn'),
                        'executionRoleArn': out.get('P20CInventoryExecutionRoleArn'),
                        'secretArn': out.get('P20CInventoryDbSecretArn')}
            task = definition(backend, HOST, ca, 'inventory', fixture, 'inventory', inventory_security=security)
            validate_inventory_request(task)
            emit(a.output, 'register-c-inventory.json', task)
            emit(a.output, 'binding.json', {'status': 'READ_ONLY_INVENTORY_DEFINITION_PREPARED',
                 'executionAuthorized': False, 'stackReceiptSha256': fingerprint(receipt),
                 'taskDefinitionSha256': fingerprint(task), 'requiresSeparateRegistrationAndRunTaskApproval': True})
            return 0
        if a.prepare_inventory_provisioner_definition:
            require(a.prepared is not None and a.database_receipt is not None,
                    'Prepared plan, stack receipt, and fresh database receipt are required')
            plan = load(a.prepared / 'plan-c.json')
            require(fingerprint({k: v for k, v in plan.items() if k != 'planHash'}) == plan['planHash'], 'Prepared plan hash changed')
            require(plan['account'] == ACCOUNT and plan['workIdentifier'] == WORK
                    and plan['fixtureSha256'] == hashlib.sha256(fixture.encode()).hexdigest()
                    and plan['sourceBackendDefinitionSha256'] == fingerprint(backend)
                    and plan['preparerSha256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'Prepared sources/target differ from current local code')
            stack_receipt = load(a.prepare_inventory_provisioner_definition)
            require(stack_receipt.get('identity', {}).get('Account') == ACCOUNT
                    and stack_receipt.get('region') == 'us-east-1'
                    and stack_receipt.get('stack', {}).get('StackName') == 'SagrilaftStack-' + LAB
                    and stack_receipt.get('stack', {}).get('StackStatus') in
                    {'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'},
                    'Provisioner roles/secrets must come from the exact terminal P20 stack')
            db_receipt = load(a.database_receipt)
            validate_inventory_provisioner_database_receipt(db_receipt)
            out = stack_receipt.get('outputs', {})
            task = definition(backend, HOST, ca, 'inventory-provisioner',
                              (ROOT / 'backend/scripts/p20_c_provision_inventory.py').read_text(),
                              'provision-inventory', provision_security={
                'taskRoleArn': out.get('P20CInventoryProvisionTaskRoleArn'),
                'executionRoleArn': out.get('P20CInventoryProvisionExecutionRoleArn'),
                'adminSecretArn': out.get('DbSecretArn'),
                'inventorySecretArn': out.get('P20CInventoryDbSecretArn'),
            })
            validate_inventory_provisioner_request(task)
            emit(a.output, 'register-c-inventory-provisioner.json', task)
            emit(a.output, 'binding.json', {'status': 'ONE_SHOT_PROVISIONER_DEFINITION_PREPARED',
                 'executionAuthorized': False, 'stackReceiptSha256': fingerprint(stack_receipt),
                 'databaseReceiptSha256': fingerprint(db_receipt), 'taskDefinitionSha256': fingerprint(task),
                 'requiresSeparateRegistrationAndRunTaskApproval': True,
                 'databaseTargetConfirmedFromReceipt': WORK, 'databaseCredentialsTested': False})
            return 0
        if a.bind_ddl_receipt or a.bind_restore_receipt or a.bind_restore_endpoint:
            require(a.prepared is not None, 'Original prepared plan required')
            plan = load(a.prepared / 'plan-c.json')
            require(fingerprint({k: v for k, v in plan.items() if k != 'planHash'}) == plan['planHash'], 'Prepared plan hash changed')
            require(plan['account'] == ACCOUNT and plan['workIdentifier'] == WORK and plan['restoreIdentifier'] == RESTORE
                    and plan['snapshotIdentifier'] == SNAPSHOT, 'Prepared plan scope changed')
            require(plan['fixtureSha256'] == hashlib.sha256(fixture.encode()).hexdigest()
                    and plan['sourceBackendDefinitionSha256'] == fingerprint(backend)
                    and plan['preparerSha256'] in {LEGACY_PREPARER_SHA256,
                        hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, 'Source changed since preparation')
            if a.bind_ddl_receipt:
                receipt = load(a.bind_ddl_receipt)
                h = validate_containment(receipt, plan['runId'], plan['planHash'], plan['serviceNames'], plan['stoppedTemplateSha256'])
                emit(a.output, 'register-c-incompatibility.json', definition(backend, HOST, ca, 'incompatibility', fixture, 'incompatibility', h))
                emit(a.output, 'binding.json', {'status': 'DDL_INPUT_BOUND_FOR_REVIEW', 'receiptSha256': h, 'executionAuthorized': False})
            else:
                receipt = load(a.bind_restore_endpoint or a.bind_restore_receipt)
                h = validate_restore_receipt(receipt, load(a.prepared / 'restore-snapshot.json'), plan,
                                             require_controls=not bool(a.bind_restore_endpoint))
                if a.bind_restore_endpoint:
                    emit(a.output, 'register-c-verify-restored.json', definition(backend, h, ca, 'verify-restored', fixture, 'verify-restored'))
                    emit(a.output, 'binding.json', {'status': 'READ_ONLY_RESTORED_QUERY_BOUND_FOR_REVIEW', 'host': h, 'executionAuthorized': False})
                    return 0
                require(a.bind_restore_receipt and a.live_template_receipt,
                        'Safe repoint generation requires a verified restore and a fresh live template receipt')
                live_receipt = load(a.live_template_receipt)
                live_template = validate_live_repoint_receipt(live_receipt, plan)
                target_template = repoint_template_from_live(live_template, h)
                emit(a.output, 'repoint-stopped.template.json', target_template)
                emit(a.output, 'repoint-diff-summary.json', {
                    'status': 'LOCAL_DIFF_ONLY', 'executionAuthorized': False,
                    'liveResourceCount': len(live_template['Resources']),
                    'targetResourceCount': len(target_template['Resources']),
                    'addedResources': sorted(set(target_template['Resources']) - set(live_template['Resources'])),
                    'removedResources': sorted(set(live_template['Resources']) - set(target_template['Resources'])),
                    'replacementTaskDefinitions': sorted(task_names(live_template)[n][0] for n in ('backend','keycloak','migration')),
                    'dependentServices': ['EcsFargateBackendService10F4F273','EcsFargateKeycloakServiceD629B160'],
                    'allServiceDesiredCounts': sorted({r['Properties']['DesiredCount'] for r in target_template['Resources'].values() if r['Type']=='AWS::ECS::Service'}),
                    'outputChanges': ['EcsDatabaseHost'],
                    'host': h,
                })
                emit(a.output, 'register-c-backend-restored.json', definition(backend, h, ca, 'backend-restored'))
                emit(a.output, 'register-c-verify-restored.json', definition(backend, h, ca, 'verify-restored', fixture, 'verify-restored'))
                smoke = (e / 'scenario-b-functional-smoke-20261014T155828Z/smoke-payload.py').read_text()
                smoke = re.sub(r'^CA_PEM=.*$', lambda _: 'CA_PEM=' + repr(ca), smoke, flags=re.MULTILINE)
                smoke = smoke.replace("HOST='" + HOST + "'", 'HOST=' + repr(h))
                smoke = smoke.replace("OLD_CITY='P20 prueba de actualización'", "OLD_CITY='P20 prueba de recuperación B'")
                smoke = smoke.replace("\nCITY='P20 prueba de recuperación B'", "\nCITY='P20 prueba de recuperación C'", 1)
                smoke = smoke.replace('P20_B_FUNCTIONAL', 'P20_C_FUNCTIONAL')
                smoke = smoke.replace("write_attempted=False", "if os.environ.get('P20_C_ALLOW_SYNTHETIC_WRITE') != 'true':\n print('P20 C smoke requires separate synthetic-write authorization');sys.exit(0)\nwrite_attempted=False", 1)
                smoke = smoke.replace("def schema():\n", "def schema():\n require(conn.execute(\"SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='formularios' AND column_name='p20_c_razon_social'\").fetchone()[0]==0,'Incompatible column remains')\n", 1)
                compile(smoke, 'c-recovery-smoke', 'exec')
                (a.output / 'smoke-restored.py').write_text(smoke)
                emit(a.output, 'smoke-exec-command.json', {'command': 'env P20_C_ALLOW_SYNTHETIC_WRITE=true ' + __import__('shlex').join(command(smoke)),
                     'requiresSeparateWriteApproval': True, 'maximumPutAttempts': 1})
                emit(a.output, 'binding.json', {'status': 'RESTORED_INPUTS_BOUND_FOR_REVIEW', 'host': h, 'executionAuthorized': False})
            return 0
        plan = {'status': 'LOCAL_REVIEW_ONLY', 'executionAuthorized': False, 'account': ACCOUNT, 'region': 'us-east-1',
                'environment': LAB, 'runId': uuid.uuid4().hex, 'workIdentifier': WORK, 'workHost': HOST,
                'snapshotIdentifier': SNAPSHOT, 'restoreIdentifier': RESTORE, 'restoreEndpoint': None,
                'baselineTemplateSha256': fingerprint(baseline), 'stoppedTemplateSha256': fingerprint(stopped),
                'backendDigest': DIGEST, 'fixtureSha256': hashlib.sha256(fixture.encode()).hexdigest(),
                'sourceBackendDefinitionSha256': fingerprint(backend),
                'preparerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'pending': ['AWS/SQL preflight approval', 'Effective permissions', 'Current state and fresh backup',
                            'Read-only PostgreSQL role and secret password synchronization',
                            'Dedicated C task role/execution role and their verified stack outputs',
                            'New endpoint binding', 'Approval per mutation phase']}
        plan['serviceNames'] = [s['serviceName'] for s in load(closure / 'services.json')['services']]
        plan['planHash'] = fingerprint(plan)
        emit(a.output, 'plan-c.json', plan)
        emit(a.output, 'lock-requirements.json', {
            'status': 'NO_LOCK_OPERATION_IN_LOCAL_PREPARATION',
            'executionAuthorized': False,
            'existingCLockMustNotBeReplaced': True,
            'required': 'Read-only reconciliation of the already-approved C lock before any later phase'})
        emit(a.output, 'stop-services.template.json', stopped)
        tags = [{'Key': 'Project', 'Value': 'sagrilaft'}, {'Key': 'Environment', 'Value': LAB}, {'Key': 'Scenario', 'Value': 'C'}]
        emit(a.output, 'create-snapshot.json', {'DBInstanceIdentifier': WORK, 'DBSnapshotIdentifier': SNAPSHOT, 'Tags': tags})
        emit(a.output, 'restore-snapshot.json', {'DBInstanceIdentifier': RESTORE, 'DBSnapshotIdentifier': SNAPSHOT,
             'DBInstanceClass': 'db.t3.medium', 'DBSubnetGroupName': db['DBSubnetGroup']['DBSubnetGroupName'],
             'VpcSecurityGroupIds': [SG], 'AvailabilityZone': 'us-east-1b', 'MultiAZ': False, 'PubliclyAccessible': False,
             'StorageType': 'gp2', 'AllocatedStorage': 100, 'DBParameterGroupName': 'default.postgres16',
             'OptionGroupName': 'default:postgres-16', 'CopyTagsToSnapshot': True, 'DeletionProtection': False,
             'BackupRetentionPeriod': 1, 'AutoMinorVersionUpgrade': db['AutoMinorVersionUpgrade'], 'Tags': tags,
             'CACertificateIdentifier': 'rds-ca-rsa2048-g1'})
        emit(a.output, 'inventory-definition-requirements.json', {
            'status': 'WAITING_FOR_APPROVED_P20_STACK_OUTPUTS_AND_DB_ROLE',
            'executionAuthorized': False,
            'taskFamily': 'sagrilaft-' + LAB + '-c-inventory',
            'taskRoleName': 'sagrilaft-' + LAB + '-c-inventory-task',
            'executionRoleName': 'sagrilaft-' + LAB + '-c-inventory-execution',
            'secretName': 'sagrilaft/' + LAB + '/c_inventory_db_credentials',
            'requiredStackOutputs': ['P20CInventoryDbSecretArn', 'P20CInventoryTaskRoleArn',
                                     'P20CInventoryExecutionRoleArn'],
            'databaseRoleSql': 'backend/scripts/p20_c_inventory_role.sql',
            'warning': 'Do not register a task definition from the historical register-c-inventory.json artifact.'})
        emit(a.output, 'register-c-verify-incompatible.json', definition(backend, HOST, ca, 'verify-incompatible', fixture, 'verify-incompatible'))
        emit(a.output, 'register-c-backend-incompatible.json', definition(backend, HOST, ca, 'backend-incompatible'))
        emit(a.output, 'task-network.json', {'awsvpcConfiguration': {'subnets': ['subnet-06d7476a355f2422e', 'subnet-0765cf0718cd64c84'],
             'securityGroups': [outputs['EcsSecurityGroupId']], 'assignPublicIp': 'DISABLED'}})
        emit(a.output, 'parameters.json', [{'ParameterKey': v['ParameterKey'], 'UsePreviousValue': True} for v in load(closure / 'stack.json')['Stacks'][0]['Parameters']])
        emit(a.output, 'resources.json', {'bucket': outputs['S3Bucket'], 'lockKey': '_deployment/SagrilaftStack-' + LAB + '.lock',
             'cfnRole': load(closure / 'stack.json')['Stacks'][0]['RoleARN'], 'taskRole': backend['taskRoleArn'],
             'executionRole': backend['executionRoleArn'], 'kmsKey': KMS, 'vpc': VPC, 'rdsSecurityGroup': SG})
        print('Local C inputs prepared. No AWS calls. DDL and restored inputs require fresh receipt binding.')
        return 0
    except (ValueError, KeyError, OSError, StopIteration) as exc:
        print('Local preparation blocked: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
