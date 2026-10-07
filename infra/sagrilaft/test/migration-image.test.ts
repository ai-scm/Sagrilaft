import { deepStrictEqual, equal, match, throws } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(context: Record<string, unknown> = {}) {
  const app = new App({ context: {
    environment: 'staging',
    imageTag: 'release-old',
    proveedorListasCautela: 'deshabilitado',
    ...context,
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON();
}

function migration(template: ReturnType<typeof synth>) {
  const entries = Object.entries(template.Resources) as Array<[string, any]>;
  const result = entries.find(([, resource]) =>
    resource.Type === 'AWS::ECS::TaskDefinition'
    && resource.Properties.ContainerDefinitions.some((container: any) => container.Name === 'migration'));
  if (!result) throw new Error('Migration task definition missing');
  return { id: result[0], container: result[1].Properties.ContainerDefinitions[0] };
}

function assertMigrationTag(template: ReturnType<typeof synth>, tag: string) {
  const { container } = migration(template);
  match(JSON.stringify(container.Image), new RegExp(`:${tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`));
  equal(container.Environment.find((item: any) => item.Name === 'GIT_SHA').Value, tag);
  equal(container.Environment.find((item: any) => item.Name === 'RUN_MODE').Value, 'migrate');
  equal(template.Outputs.EcsMigrationImageTag.Value, tag);
}

for (const environment of ['staging', 'prod']) {
  test(`${environment}: public ALB inserts HSTS on HTTPS responses`, () => {
    const loadBalancer = Object.values(synth({ environment }).Resources)
      .find((resource: any) => resource.Type === 'AWS::ElasticLoadBalancingV2::LoadBalancer') as any;
    const hsts = loadBalancer.Properties.LoadBalancerAttributes.find(
      (attribute: any) => attribute.Key === 'routing.http.response.strict_transport_security.header_value',
    );
    equal(hsts?.Value, 'max-age=31536000');
  });

  test(`${environment}: RDS uses the selected db.t3.medium instance class`, () => {
    const database = Object.values(synth({ environment }).Resources)
      .find((resource: any) => resource.Type === 'AWS::RDS::DBInstance') as any;
    equal(database.Properties.DBInstanceClass, 'db.t3.medium');
    equal(database.Properties.MultiAZ, false);
    equal(database.Properties.BackupRetentionPeriod, 7);
  });

  test(`${environment}: all four ECR repositories are immutable without exclusions`, () => {
    const repositories = Object.values(synth({ environment }).Resources)
      .filter((resource: any) => resource.Type === 'AWS::ECR::Repository') as any[];
    equal(repositories.length, 4);
    for (const repository of repositories) {
      equal(repository.Properties.ImageTagMutability, 'IMMUTABLE');
      equal(repository.Properties.ImageTagMutabilityExclusionFilters, undefined);
    }
  });

  test(`${environment}: explicit migration tag cannot allow latest for services`, () => {
    throws(() => synth({ environment, imageTag: 'latest', migrationImageTag: 'release-new' }), /imageTag.*no latest/);
  });
  test(`${environment}: changing migration tag changes only migration image, SHA and output`, () => {
    const before = synth({ environment });
    const after = synth({ environment, migrationImageTag: 'release-new' });
    assertMigrationTag(before, 'release-old');
    assertMigrationTag(after, 'release-new');
    const oldMigration = migration(before);
    const newMigration = migration(after);
    equal(newMigration.id, oldMigration.id);

    // Compare the entire template, including service definitions, IAM and configuration.
    newMigration.container.Image = oldMigration.container.Image;
    newMigration.container.Environment.find((item: any) => item.Name === 'GIT_SHA').Value = 'release-old';
    after.Outputs.EcsMigrationImageTag.Value = 'release-old';
    deepStrictEqual(after, before);
  });

  test(`${environment}: omitted migration tag preserves bootstrap with no active tasks`, () => {
    const template = synth({ environment, imageTag: 'bootstrap-placeholder', desiredCount: 0 });
    assertMigrationTag(template, 'bootstrap-placeholder');
    const services = Object.values(template.Resources).filter((resource: any) => resource.Type === 'AWS::ECS::Service') as any[];
    equal(services.length, 4);
    for (const service of services) equal(service.Properties.DesiredCount, 0);
  });

  test(`${environment}: migration override does not bypass required service tag`, () => {
    throws(() => synth({ environment, imageTag: '', migrationImageTag: 'release-new' }), /requiere -c imageTag/);
  });

  test(`${environment}: latest migration tag is rejected`, () => {
    throws(() => synth({ environment, migrationImageTag: 'latest' }), /no latest/);
  });
}

test('development fallback remains dev when neither tag is supplied', () => {
  assertMigrationTag(synth({ environment: 'dev', imageTag: '' }), 'dev');
});

test('invalid explicit migration tags fail before synthesis', () => {
  for (const migrationImageTag of ['', ' ', ' release', 'repo:tag', 'sha256:abc', '-release', 'a'.repeat(129)]) {
    throws(() => synth({ migrationImageTag }), /migrationImageTag invalido/);
  }
});
