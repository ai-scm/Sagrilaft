#!/usr/bin/env python3
"""Prepare P20 B files locally. No AWS calls, deploy, RunTask or subprocesses."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import zlib

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'backend', 'frontend', 'portal', 'keycloak', 'migration'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def inline_command(source, argv=(), ca_pem=None):
    payload = base64.b64encode(zlib.compress(json.dumps({'source': source, 'argv': list(argv), 'ca': ca_pem}).encode())).decode()
    boot = "import base64,json,zlib,sys,tempfile;from pathlib import Path\np=json.loads(zlib.decompress(base64.b64decode(" + repr(payload) + ")))\n"
    if ca_pem:
        boot += "with tempfile.TemporaryDirectory(prefix='p20-b-ca-') as d:\n c=Path(d)/'ca.pem';c.write_text(p['ca']);sys.argv=['p20_b_migrate',*p['argv'],'--ssl-root-cert',str(c)];exec(compile(p['source'],'p20_b_migrate','exec'))"
    else:
        boot += "sys.argv=['p20_b_unhealthy',*p['argv']];exec(compile(p['source'],'p20_b_unhealthy','exec'))"
    command = ['python', '-c', boot]
    require(len(json.dumps({'containerOverrides': [{'name': 'migration', 'command': command}]}).encode()) < 8192,
            'Migration command exceeds ECS override limit')
    return command


def backend_id(template):
    found = [key for key, r in template['Resources'].items() if r['Type'] == 'AWS::ECS::TaskDefinition'
             and any(c.get('Name') == 'backend' for c in r['Properties'].get('ContainerDefinitions', []))]
    require(len(found) == 1, 'Expected one backend definition')
    return found[0]


def assert_b_transition(baseline, candidate, expected_image, expected_command):
    """Permit only the pinned backend image, inert command, and two fixture env values."""
    restored = copy.deepcopy(candidate)
    key = backend_id(baseline)
    original = baseline['Resources'][key]['Properties']['ContainerDefinitions'][0]
    changed = restored['Resources'][key]['Properties']['ContainerDefinitions'][0]
    require(not original.get('EntryPoint') and not changed.get('EntryPoint'), 'Entrypoint must be empty')
    require(changed['Image'] == expected_image and changed['Command'] == expected_command, 'Unexpected candidate image/command')
    env = {x['Name']: x['Value'] for x in changed.get('Environment', [])}
    require(env.get('RUN_MODE') == 'p20-b-unhealthy' and env.get('P20_B_FORCE_UNHEALTHY') == 'true', 'Missing inert B flags')
    changed['Image'] = copy.deepcopy(original['Image'])
    if 'Command' in original:
        changed['Command'] = copy.deepcopy(original['Command'])
    else:
        changed.pop('Command', None)
    require(not any(e['Name'] == 'P20_B_FORCE_UNHEALTHY' for e in original.get('Environment', [])), 'Baseline already contains B fault')
    changed['Environment'] = [x for x in changed.get('Environment', []) if x['Name'] != 'P20_B_FORCE_UNHEALTHY']
    for item in changed['Environment']:
        if item['Name'] == 'RUN_MODE': item['Value'] = 'server'
    require(restored == baseline, 'B changes resources, counts, DB, secrets, images or configuration outside backend fixture')


def prepare(baseline, outputs, migration_definition, backend_digest, ca_pem, source_root=ROOT):
    environment = outputs['EcsClusterName'].removeprefix('sagrilaft-')
    require(bool(re.fullmatch(r'p20-[a-f0-9]{12}', environment)), 'P20 only')
    host = outputs['EcsDatabaseHost']
    identifier = host.split('.')[0]
    require(bool(re.fullmatch(re.escape(environment) + r'-c7-test-[0-9]{8}', identifier)), 'Only c7-test clone')
    require(bool(re.fullmatch(re.escape(identifier) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Unexpected clone endpoint')
    require(host != outputs['RdsEndpoint'] and outputs['EcsDesiredCount'] == '1', 'Unexpected original DB/common capacity')
    require(bool(re.fullmatch(r'874641912777\.dkr\.ecr\.us-east-1\.amazonaws\.com/sagrilaft-' + re.escape(environment) + r'-backend', outputs['EcrBackendUri'])), 'Wrong ECR account/region/repository')
    require(bool(re.fullmatch(r'sha256:[a-f0-9]{64}', backend_digest)), 'Backend digest missing')
    require('-----BEGIN CERTIFICATE-----' in ca_pem and len(ca_pem) < 3000, 'Provide the RSA2048 RDS trust anchor, not the entire bundle')
    names = {}
    service_count = 0
    for key, r in baseline['Resources'].items():
        if r['Type'] == 'AWS::ECS::TaskDefinition':
            containers = r['Properties']['ContainerDefinitions']
            require(len(containers) == 1 and containers[0]['Name'] not in names, 'Ambiguous task definitions')
            names[containers[0]['Name']] = containers[0]
        if r['Type'] == 'AWS::ECS::Service':
            service_count += 1
            require(r['Properties']['DesiredCount'] == 1 and r['Properties']['DeploymentConfiguration']['DeploymentCircuitBreaker'] == {'Enable': True, 'Rollback': True}, 'Four stable services/circuit breaker required')
    require(set(names) == KINDS and service_count == 4, 'Expected five definitions and four services')
    for name, keys in {'backend': ['DATABASE_HOST', 'KEYCLOAK_DB_URL'], 'migration': ['DATABASE_HOST', 'KEYCLOAK_DB_URL'], 'keycloak': ['KC_DB_URL']}.items():
        env = {x['Name']: x['Value'] for x in names[name]['Environment']}
        require(all(env.get(k) == (host if k == 'DATABASE_HOST' else f'jdbc:postgresql://{host}:5432/sagrilaft') for k in keys), 'Task points outside working clone')
    backend_env = {x['Name']: x['Value'] for x in names['backend']['Environment']}
    require(backend_env.get('P20_RUN_ID') == environment and backend_env.get('ZOHO_SIGN_ENABLED') == 'false' and backend_env.get('RUN_MODE') == 'server', 'Unsafe P20 baseline')
    health_source = (source_root / 'backend/scripts/p20_b_unhealthy.py').read_text()
    migration_source = (source_root / 'backend/scripts/p20_b_migrate.py').read_text()
    unhealthy_command = inline_command(health_source)
    image = outputs['EcrBackendUri'] + '@' + backend_digest
    candidate = copy.deepcopy(baseline)
    container = candidate['Resources'][backend_id(candidate)]['Properties']['ContainerDefinitions'][0]
    container['Image'], container['Command'] = image, unhealthy_command
    for item in container['Environment']:
        if item['Name'] == 'RUN_MODE': item['Value'] = 'p20-b-unhealthy'
    container['Environment'].append({'Name': 'P20_B_FORCE_UNHEALTHY', 'Value': 'true'})
    assert_b_transition(baseline, candidate, image, unhealthy_command)
    # Standalone task registration input; never replace the project's migration definition.
    register = {key: copy.deepcopy(migration_definition[key]) for key in ('taskRoleArn', 'executionRoleArn', 'networkMode', 'requiresCompatibilities', 'cpu', 'memory', 'runtimePlatform') if key in migration_definition}
    require(migration_definition.get('taskDefinitionArn') == outputs['EcsMigrationTaskDefinitionArn'], 'Migration evidence is from another definition')
    require(all(register.get(k, '').startswith('arn:aws:iam::874641912777:role/SagrilaftStack-p20-')
                for k in ('taskRoleArn', 'executionRoleArn')), 'Roles outside P20 scope')
    require(register.get('networkMode') == 'awsvpc' and 'FARGATE' in register.get('requiresCompatibilities', []), 'Fargate migration task required')
    register['family'] = 'sagrilaft-' + environment + '-b-migration'
    c = copy.deepcopy(migration_definition['containerDefinitions'][0])
    require(c['name'] == 'migration' and not c.get('entryPoint'), 'Unsafe migration entrypoint')
    require(c.get('logConfiguration', {}).get('options', {}).get('awslogs-group') == f'/sagrilaft/{environment}/ecs/migration', 'Logs outside P20')
    c['image'], c['entryPoint'] = image, []
    c['environment'] = [{'name': 'P20_RUN_ID', 'value': environment}, {'name': 'DATABASE_HOST', 'value': host},
                        {'name': 'DATABASE_NAME', 'value': 'sagrilaft'}, {'name': 'ZOHO_SIGN_ENABLED', 'value': 'false'},
                        {'name': 'RUN_MODE', 'value': 'p20-b-migration'}]
    secrets = {x['name']: x for x in c.get('secrets', [])}
    require({'DB_USER', 'DB_PASSWORD'} <= secrets.keys(), 'Missing P20 credentials')
    require(all(secrets[k]['valueFrom'] == outputs['DbSecretArn'] + suffix for k, suffix in [('DB_USER', ':username::'), ('DB_PASSWORD', ':password::')]), 'Credentials not from P20 DB secret')
    c['secrets'] = [secrets[k] for k in ('DB_USER', 'DB_PASSWORD')]
    c['command'] = inline_command(migration_source, ['--db-identifier', identifier, '--expected-host', host, '--apply'], ca_pem)
    c.pop('healthCheck', None)
    register['containerDefinitions'] = [c]
    register['tags'] = [{'key': 'Project', 'value': 'sagrilaft'}, {'key': 'Environment', 'value': environment}]
    plan = {'status': 'LOCAL_REVIEW_ONLY', 'executionAuthorized': False, 'environment': environment,
            'reuseExistingAStackProposed': True, 'reuseExistingAStackApproved': False,
            'account': '874641912777', 'region': 'us-east-1', 'databaseIdentifier': identifier, 'databaseHost': host,
            'baselineTemplateSha256': fingerprint(baseline), 'candidateTemplateSha256': fingerprint(candidate),
            'rollbackTemplateSha256': fingerprint(baseline), 'backendImage': image, 'newImagesRequired': False,
            'mainAlembicRevisionBeforeAndAfter': 'c7a1c1a65662', 'fixtureRevision': 'p20b_expand_01',
            'fixtureVersionTable': 'public.p20_b_alembic_version', 'addedColumn': 'public.formularios.p20_b_probe',
            'onlyServiceChanged': 'backend', 'allFourDesiredCounts': 1, 'migrationRunsOnRollback': False,
            'sourceSha256': {'health': hashlib.sha256(health_source.encode()).hexdigest(), 'migration': hashlib.sha256(migration_source.encode()).hexdigest()},
            'pending': ['Explicit approval to reuse the closed A stack instead of a separate B stack',
                        'Approval of isolated fixture scope/version table', 'Fresh AWS preflight only before approved execution',
                        'Snapshot of current synthetic control if agreed; c7-base predates it',
                        'Verify pinned backend image config has empty entrypoint', 'Review change set: backend task/service only',
                        'Separate approvals for migration, unhealthy activation, any explicit rollback and functional writes']}
    return {'plan-b.json': plan, 'activate-unhealthy.template.json': candidate, 'rollback-baseline.template.json': copy.deepcopy(baseline), 'register-b-migration.json': register}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--ca-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.evidence_root
        closed = json.loads((root / 'scenario-a-formal-closure-20261014/result.json').read_text())
        require(closed['scenarioAClosed'] and closed['locksReleasedConditionally'], 'A must be closed before preparing B')
        baseline = json.loads((root / 'scenario-a-observer-loss-execution-20261014/p20-a-baseline.json').read_text())
        tasks = json.loads((root / 'scenario-a-observer-loss-execution-20261014/post-baseline-tasks.json').read_text())['tasks']
        backend = next(t for t in tasks if t['containers'][0]['name'] == 'backend')
        definition = json.loads((root / 'resource-retention-review-20261014T124300Z/definition-migration.json').read_text())['data']['taskDefinition']
        files = prepare(baseline['template'], baseline['outputs'], definition, backend['containers'][0]['imageDigest'], args.ca_file.read_text())
        args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name, value in files.items():
            path = args.output / name
            path.write_text(json.dumps(value, indent=2) + '\n')
            path.chmod(0o600)
        print('Local P20 B artifacts prepared; no AWS operations performed')
        return 0
    except (ValueError, KeyError, OSError, StopIteration) as exc:
        print('Preparation blocked: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
