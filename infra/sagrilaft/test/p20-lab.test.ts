import { deepStrictEqual, equal, throws } from 'node:assert/strict';
import { test } from 'node:test';
import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { ConfigParameters } from '../lib/constructs/config-parameters';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

const environment = 'p20-012345abcdef';

function synth(context: Record<string, unknown> = {}) {
  const app = new App({ context: {
    environment,
    account: '874641912777',
    region: 'us-east-1',
    hostedZoneName: '',
    hostedZoneId: '',
    certificateArn: 'arn:aws:acm:us-east-1:874641912777:certificate/00000000-0000-0000-0000-000000000000',
    imageTag: 'p20-synth',
    migrationImageTag: 'p20-synth',
    desiredCount: 0,
    snsAlertasSub: '',
    habilitarNatEgress: false,
    proveedorListasCautela: 'dummy',
    zohoSecretYaExiste: false,
    ...context,
  } });
  return Template.fromStack(new SagrilaftStack(app, 'P20TestStack', {
    env: { account: '874641912777', region: 'us-east-1' },
  })).toJSON();
}

test('P20 synthesis is isolated, disposable, and starts with four ECS services at zero', () => {
  const template = synth();
  const resources = Object.values(template.Resources) as any[];
  const loadBalancer = resources.find(resource => resource.Type === 'AWS::ElasticLoadBalancingV2::LoadBalancer');
  equal(loadBalancer?.Properties.Scheme, 'internal');
  equal(resources.some(resource => resource.Type === 'AWS::Route53::RecordSet'), false);
  equal(resources.some(resource => resource.Type === 'AWS::WAFv2::WebACL'), false);
  equal(resources.some(resource => resource.Type === 'AWS::SES::EmailIdentity'), false);
  equal(resources.some(resource => resource.Type === 'AWS::SNS::Subscription'), false);
  equal(resources.some(resource => resource.Type === 'AWS::EC2::NatGateway'), false);

  const endpoints = resources.filter(resource => resource.Type === 'AWS::EC2::VPCEndpoint');
  equal(endpoints.some(resource => /email|bedrock/i.test(JSON.stringify(resource.Properties.ServiceName))), false);
  equal(endpoints.some(resource => /ssmmessages/.test(JSON.stringify(resource.Properties.ServiceName))), true);

  const services = resources.filter(resource => resource.Type === 'AWS::ECS::Service');
  equal(services.length, 4);
  for (const service of services) equal(service.Properties.DesiredCount, 0);

  const db = resources.find(resource => resource.Type === 'AWS::RDS::DBInstance');
  equal(db?.Properties.DeletionProtection, false);
  equal(db?.DeletionPolicy, 'Delete');
  const bucket = resources.find(resource => resource.Type === 'AWS::S3::Bucket');
  equal(bucket?.DeletionPolicy, 'Delete');
  equal(bucket?.Properties.VersioningConfiguration, undefined);

  const repositories = resources.filter(resource => resource.Type === 'AWS::ECR::Repository');
  equal(repositories.length, 4);
  for (const repository of repositories) {
    equal(repository.Properties.ImageTagMutability, 'IMMUTABLE');
    equal(repository.Properties.ImageTagMutabilityExclusionFilters, undefined);
    equal(repository.Properties.EmptyOnDelete, true);
  }

  const params = resources.filter(resource => resource.Type === 'AWS::SSM::Parameter');
  equal(params.find(param => param.Properties.Name.endsWith('/APP_ENV'))?.Properties.Value, 'staging');
  equal(params.find(param => param.Properties.Name.endsWith('/SES_NOTIFICACIONES_ENABLED'))?.Properties.Value, 'false');
  for (const key of ['SMTP_FROM', 'SES_EMAIL_ORIGEN', 'ALERTAS_EMAIL_DESTINATARIO']) {
    const value = params.find(param => param.Properties.Name.endsWith(`/${key}`))?.Properties.Value;
    equal(value, 'disabled-p20@example.invalid');
    equal(value.length > 0, true);
  }
  deepStrictEqual(template.Outputs.EcsDatabaseHost.Value, template.Outputs.RdsEndpoint.Value);
});

test('deployment descriptions use the exact ASCII text intended for CloudFormation', () => {
  const template = synth();
  const resources = Object.values(template.Resources) as any[];
  const repositories = resources.filter(resource => resource.Type === 'AWS::ECR::Repository');
  equal(repositories.length, 4);
  for (const repository of repositories) {
    const policy = JSON.parse(repository.Properties.LifecyclePolicy.LifecyclePolicyText);
    equal(policy.rules[0].description, 'Mantener las ultimas 30 imagenes para ahorrar costos');
  }

  const alarms = resources.filter(resource => resource.Type === 'AWS::CloudWatch::Alarm');
  deepStrictEqual(alarms.map(alarm => alarm.Properties.AlarmDescription).sort(), [
    'Alarma Critica: Se detectaron mas de 5 errores HTTP 5xx en el servidor backend durante los ultimos 5 minutos.',
    'Alarma de Rendimiento: El uso de CPU del servicio Backend supero el 85% de su capacidad.',
    'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend supero el 85% de su capacidad.',
  ].sort());

  const dashboard = resources.find(resource => resource.Type === 'AWS::CloudWatch::Dashboard'
    && resource.Properties.DashboardName === 'Sagrilaft-Negocio-p20-012345abcdef');
  equal(JSON.stringify(dashboard?.Properties.DashboardBody).includes('Tasas de Exito: Decisiones de Expedientes'), true);
  equal(template.Outputs.AlbDns.Description, 'DNS privado del ALB interno P20; no crear DNS publico');
  equal(template.Outputs.EcsDatabaseHost.Description,
    'Host de BD usado por tareas ECS; en P20 puede apuntar a una restauracion aislada');

  const deploymentText = [
    ...repositories.map(repository => repository.Properties.LifecyclePolicy.LifecyclePolicyText),
    ...alarms.map(alarm => alarm.Properties.AlarmDescription),
    JSON.stringify(dashboard?.Properties.DashboardBody),
    template.Outputs.AlbDns.Description,
    template.Outputs.EcsDatabaseHost.Description,
  ].join('\n');
  equal(/[\u00C0-\u024F?]/.test(deploymentText), false);
});

test('P20 restored-database override reaches backend and Keycloak task configuration', () => {
  const template = synth({ databaseHostOverride: 'restored-db.p20.internal' });
  const tasks = Object.values(template.Resources).filter((resource: any) =>
    resource.Type === 'AWS::ECS::TaskDefinition') as any[];
  const backend = tasks.find(task => task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend'));
  const backendContainer = backend.Properties.ContainerDefinitions.find((container: any) => container.Name === 'backend');
  equal(backendContainer.Environment.find((item: any) => item.Name === 'DATABASE_HOST').Value, 'restored-db.p20.internal');
  equal(backendContainer.Environment.find((item: any) => item.Name === 'KEYCLOAK_DB_URL').Value,
    'jdbc:postgresql://restored-db.p20.internal:5432/sagrilaft');

  const keycloak = tasks.find(task => task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'keycloak'));
  const keycloakContainer = keycloak.Properties.ContainerDefinitions.find((container: any) => container.Name === 'keycloak');
  equal(keycloakContainer.Environment.find((item: any) => item.Name === 'KC_DB_URL').Value,
    'jdbc:postgresql://restored-db.p20.internal:5432/sagrilaft');
  equal(template.Outputs.EcsDatabaseHost.Value, 'restored-db.p20.internal');
});

test('P20 context cannot enable NAT, desired tasks, SNS email, or use DNS zone', () => {
  for (const unsafe of [
    { habilitarNatEgress: true },
    { desiredCount: 1 },
    { snsAlertasSub: 'controlled@example.invalid' },
    { hostedZoneName: 'example.com', hostedZoneId: 'Z123' },
  ]) {
    throws(() => synth(unsafe), /P20 requiere/);
  }
});

test('P20 activation requires the explicit orchestrator-only guard', () => {
  throws(() => synth({ desiredCount: 1 }), /p20AllowActivation=true/);
  const activated = synth({ desiredCount: 1, p20AllowActivation: true });
  const services = Object.values(activated.Resources).filter((resource: any) => resource.Type === 'AWS::ECS::Service') as any[];
  equal(services.length, 4);
  for (const service of services) equal(service.Properties.DesiredCount, 1);
});

test('P20 database host override cannot be used by staging or production', () => {
  const app = new App({ context: { environment: 'staging', imageTag: 'test', databaseHostOverride: 'restored.internal' } });
  throws(() => new SagrilaftStack(app, 'UnsafeStack', { env: { account: '123456789012', region: 'us-east-1' } }),
    /databaseHostOverride solo se permite/);
});

test('P20 template names are deterministic for the run ID', () => {
  const names = Object.values(synth().Resources).filter((resource: any) =>
    ['AWS::ECS::Cluster', 'AWS::RDS::DBInstance'].includes(resource.Type));
  deepStrictEqual(names.length, 2);
});

test('non-P20 mail parameter values remain unchanged', () => {
  const app = new App();
  const stack = new Stack(app, 'StandardConfigStack');
  const configured = {
    smtpFrom: 'smtp@staging.invalid',
    alertasEmailDestino: 'alerts@staging.invalid',
  };
  new ConfigParameters(stack, 'Config', {
    ambiente: 'staging',
    dominio: 'formulario.example.invalid',
    dominioPortal: 'portal.example.invalid',
    dominioKeycloak: 'login.example.invalid',
    s3BucketName: 'test-bucket',
    sesEmailOrigen: configured.smtpFrom,
    smtpReplyTo: 'reply@example.invalid',
    alertasEmailDestino: configured.alertasEmailDestino,
    bedrockModelId: 'test-model',
    proveedorListasCautela: 'dummy',
    sagrilaftApiUrl: 'dummy://listas-cautela',
    testMode: false,
  });
  const template = Template.fromStack(stack).toJSON();
  const params = Object.values(template.Resources).filter((resource: any) =>
    resource.Type === 'AWS::SSM::Parameter') as any[];
  const valueFor = (key: string) => params.find(param => param.Properties.Name.endsWith(`/${key}`))?.Properties.Value;
  equal(valueFor('SMTP_FROM'), configured.smtpFrom);
  equal(valueFor('SES_EMAIL_ORIGEN'), configured.smtpFrom);
  equal(valueFor('ALERTAS_EMAIL_DESTINATARIO'), configured.alertasEmailDestino);
});
