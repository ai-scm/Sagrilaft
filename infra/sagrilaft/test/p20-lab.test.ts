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

test('P20-C inventory credentials and execution roles are dedicated and least-privilege', () => {
  const template = synth();
  const resources = Object.values(template.Resources) as any[];
  const inventorySecret = resources.find(resource => resource.Type === 'AWS::SecretsManager::Secret'
    && resource.Properties.Name === 'sagrilaft/p20-012345abcdef/c_inventory_db_credentials');
  equal(Boolean(inventorySecret), true);

  const roles = resources.filter(resource => resource.Type === 'AWS::IAM::Role');
  const taskRole = roles.find(role => role.Properties.RoleName === 'sagrilaft-p20-012345abcdef-c-inventory-task');
  const executionRole = roles.find(role => role.Properties.RoleName === 'sagrilaft-p20-012345abcdef-c-inventory-execution');
  const provisionTaskRole = roles.find(role => role.Properties.RoleName === 'sagrilaft-p20-012345abcdef-c-inventory-provision-task');
  const provisionExecutionRole = roles.find(role => role.Properties.RoleName === 'sagrilaft-p20-012345abcdef-c-inventory-provision-execution');
  equal(Boolean(taskRole), true);
  equal(Boolean(executionRole), true);
  equal(Boolean(provisionTaskRole), true);
  equal(Boolean(provisionExecutionRole), true);
  equal(taskRole.Properties.ManagedPolicyArns, undefined);
  equal(taskRole.Properties.Policies, undefined);
  equal(executionRole.Properties.ManagedPolicyArns, undefined);
  equal(provisionTaskRole.Properties.ManagedPolicyArns, undefined);
  equal(provisionTaskRole.Properties.Policies, undefined);
  equal(provisionExecutionRole.Properties.ManagedPolicyArns, undefined);

  const attached = resources.filter(resource => resource.Type === 'AWS::IAM::Policy'
    && JSON.stringify(resource.Properties.Roles).includes('CInventoryExecutionRole'));
  equal(attached.length, 1);
  const statements = attached.flatMap(policy => policy.Properties.PolicyDocument.Statement);
  const actions = statements.flatMap(statement => statement.Action).sort();
  deepStrictEqual(actions, [
    'ecr:BatchCheckLayerAvailability', 'ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer',
    'ecr:GetAuthorizationToken', 'logs:CreateLogStream', 'logs:PutLogEvents', 'secretsmanager:GetSecretValue',
  ].sort());
  equal(statements.some(statement => JSON.stringify(statement.Action).match(/ecs:|ssm:|ses:|sns:|s3:|bedrock:/i)), false);
  const inventoryLogStatement = statements.find(statement => statement.Sid === 'CInventoryBackendLogs');
  const inventoryLogArn = JSON.stringify(inventoryLogStatement?.Resource);
  equal(inventoryLogArn.includes('EcsFargateBackendLogGroup'), true);
  equal(inventoryLogArn.includes(':log-stream:*'), true);
  equal(inventoryLogArn.includes(':*:log-stream:*'), false);
  const provisionPolicies = resources.filter(resource => resource.Type === 'AWS::IAM::Policy'
    && JSON.stringify(resource.Properties.Roles).includes('CInventoryProvisionExecutionRole'));
  equal(provisionPolicies.length, 1);
  const provisionStatements = provisionPolicies.flatMap(policy => policy.Properties.PolicyDocument.Statement);
  deepStrictEqual(provisionStatements.flatMap(statement => statement.Action).sort(), [
    'ecr:BatchCheckLayerAvailability', 'ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer',
    'ecr:GetAuthorizationToken', 'logs:CreateLogStream', 'logs:PutLogEvents', 'secretsmanager:GetSecretValue',
  ].sort());
  const secretRead = provisionStatements.find(statement => statement.Sid === 'ReadOnlyP20DatabaseProvisioningCredentials');
  const provisionLogStatement = provisionStatements.find(statement => statement.Sid === 'CInventoryProvisionBackendLogs');
  const provisionLogArn = JSON.stringify(provisionLogStatement?.Resource);
  equal(provisionLogArn.includes('EcsFargateBackendLogGroup'), true);
  equal(provisionLogArn.includes(':log-stream:*'), true);
  equal(provisionLogArn.includes(':*:log-stream:*'), false);
  const expectedSecretRefs = ['db_credentials', 'c_inventory_db_credentials'].map(suffix => {
    const found = Object.entries(template.Resources).find(([, resource]: [string, any]) =>
      resource.Type === 'AWS::SecretsManager::Secret'
      && resource.Properties.Name === `sagrilaft/p20-012345abcdef/${suffix}`);
    return { Ref: found?.[0] };
  });
  deepStrictEqual(secretRead?.Resource.sort((a: any, b: any) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
    expectedSecretRefs.sort((a: any, b: any) => JSON.stringify(a).localeCompare(JSON.stringify(b))));
  equal(provisionStatements.some(statement => JSON.stringify(statement.Action).match(/ecs:|ssm:|ses:|sns:|s3:|bedrock:/i)), false);
  equal(JSON.stringify(template.Outputs.P20CInventoryProvisionTaskRoleArn.Value).includes('CInventoryProvisionTaskRole'), true);
  equal(JSON.stringify(template.Outputs.P20CInventoryProvisionExecutionRoleArn.Value).includes('CInventoryProvisionExecutionRole'), true);
  equal(resources.filter(resource => resource.Type === 'AWS::ECS::Service').every(service => service.Properties.DesiredCount === 0), true);
});

test('P20-C inventory-only secret and roles are absent from non-P20 synthesis', () => {
  const template = synth({ environment: 'staging' });
  const resources = Object.values(template.Resources) as any[];
  equal(resources.some(resource => resource.Type === 'AWS::SecretsManager::Secret'
    && /c_inventory_db_credentials/.test(resource.Properties.Name)), false);
  equal(resources.some(resource => resource.Type === 'AWS::IAM::Role'
    && /c-inventory/.test(resource.Properties.RoleName ?? '')), false);
  equal(template.Outputs.P20CInventoryProvisionTaskRoleArn, undefined);
  equal(template.Outputs.P20CInventoryProvisionExecutionRoleArn, undefined);
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

test('P20 restored-database override reaches every DB consumer and keeps ECS stopped', () => {
  const host = 'p20-9c67b6ea6842-c7-test-20261012.cbm5sq1kjl57.us-east-1.rds.amazonaws.com';
  const template = synth({ databaseHostOverride: host, desiredCount: 0 });
  const tasks = Object.values(template.Resources).filter((resource: any) =>
    resource.Type === 'AWS::ECS::TaskDefinition') as any[];
  const backend = tasks.find(task => task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend'));
  const backendContainer = backend.Properties.ContainerDefinitions.find((container: any) => container.Name === 'backend');
  equal(backendContainer.Environment.find((item: any) => item.Name === 'ZOHO_SIGN_ENABLED').Value, 'false');
  equal(backendContainer.Environment.find((item: any) => item.Name === 'P20_RUN_ID').Value, environment);
  equal(backendContainer.Environment.find((item: any) => item.Name === 'DATABASE_HOST').Value, host);
  equal(backendContainer.Environment.find((item: any) => item.Name === 'KEYCLOAK_DB_URL').Value,
    `jdbc:postgresql://${host}:5432/sagrilaft`);

  const keycloak = tasks.find(task => task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'keycloak'));
  const keycloakContainer = keycloak.Properties.ContainerDefinitions.find((container: any) => container.Name === 'keycloak');
  equal(keycloakContainer.Environment.find((item: any) => item.Name === 'KC_DB_URL').Value,
    `jdbc:postgresql://${host}:5432/sagrilaft`);

  const migration = tasks.find(task => task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'migration'));
  const migrationContainer = migration.Properties.ContainerDefinitions.find((container: any) => container.Name === 'migration');
  equal(migrationContainer.Environment.find((item: any) => item.Name === 'DATABASE_HOST').Value, host);
  equal(migrationContainer.Environment.find((item: any) => item.Name === 'KEYCLOAK_DB_URL').Value,
    `jdbc:postgresql://${host}:5432/sagrilaft`);
  equal(template.Outputs.EcsDatabaseHost.Value, host);
  equal(template.Outputs.EcsDesiredCount.Value, '0');
  const services = Object.values(template.Resources).filter((resource: any) => resource.Type === 'AWS::ECS::Service') as any[];
  equal(services.length, 4);
  for (const service of services) equal(service.Properties.DesiredCount, 0);

  const secretRefs = tasks.flatMap(task => task.Properties.ContainerDefinitions.flatMap((container: any) => container.Secrets ?? []));
  equal(secretRefs.length > 0, true);
  const serializedSecrets = JSON.stringify(secretRefs);
  equal(/sagrilaft\/(staging|prod)\//.test(serializedSecrets), false);
  const defaultTemplate = synth();
  const defaultTasks = Object.values(defaultTemplate.Resources).filter((resource: any) =>
    resource.Type === 'AWS::ECS::TaskDefinition') as any[];
  const defaultSecretRefs = defaultTasks.flatMap(task =>
    task.Properties.ContainerDefinitions.flatMap((container: any) => container.Secrets ?? []));
  deepStrictEqual(secretRefs, defaultSecretRefs);

  const rdsSecurityGroup = Object.entries(template.Resources).find(([, resource]: any) =>
    resource.Type === 'AWS::EC2::SecurityGroup' && resource.Properties.GroupDescription === 'RDS postgres')?.[0];
  const ecsSecurityGroup = Object.entries(template.Resources).find(([, resource]: any) =>
    resource.Type === 'AWS::EC2::SecurityGroup' && resource.Properties.GroupDescription === 'ECS Fargate services')?.[0];
  const ingress = Object.values(template.Resources).filter((resource: any) => resource.Type === 'AWS::EC2::SecurityGroupIngress') as any[];
  equal(ingress.some(rule => rule.Properties.GroupId?.['Fn::GetAtt']?.[0] === rdsSecurityGroup
    && rule.Properties.SourceSecurityGroupId?.['Fn::GetAtt']?.[0] === ecsSecurityGroup
    && rule.Properties.FromPort === 5432 && rule.Properties.ToPort === 5432), true);
});

test('P20 backend image override changes only backend and rejects non-P20 use', () => {
  const backendTag = '4d63c1356cc92b8d8d515e7147a7ac06565b0583';
  const template = synth({ imageTag: 'baseline-tag', migrationImageTag: 'migration-tag', backendImageTag: backendTag });
  const tasks = Object.values(template.Resources).filter((resource: any) =>
    resource.Type === 'AWS::ECS::TaskDefinition') as any[];
  const container = (name: string) => tasks.find(task =>
    task.Properties.ContainerDefinitions.some((item: any) => item.Name === name)
  )?.Properties.ContainerDefinitions.find((item: any) => item.Name === name);
  const backend = container('backend');
  equal(JSON.stringify(backend.Image).includes(backendTag), true);
  equal(backend.Environment.find((item: any) => item.Name === 'GIT_SHA').Value, backendTag);
  for (const name of ['frontend', 'portal', 'keycloak']) {
    equal(JSON.stringify(container(name).Image).includes('baseline-tag'), true);
  }
  equal(JSON.stringify(container('migration').Image).includes('migration-tag'), true);
  equal(Object.values(template.Resources).filter((resource: any) => resource.Type === 'AWS::ECS::Service')
    .every((service: any) => service.Properties.DesiredCount === 0), true);

  const app = new App({ context: { environment: 'staging', imageTag: 'baseline-tag', backendImageTag: backendTag } });
  throws(() => new SagrilaftStack(app, 'UnsafeBackendImageOverride', {
    env: { account: '874641912777', region: 'us-east-1' },
  }), /backendImageTag solo admite un SHA completo dentro de P20/);
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

test('P20 backend-only activation changes only backend capacity and keeps scaling disabled', () => {
  const template = synth({
    desiredCount: 0,
    backendDesiredCount: 1,
    backendMaxCapacity: 1,
    p20BackendOnlyOperation: true,
    p20AllowActivation: true,
  });
  const resources = Object.values(template.Resources) as any[];
  const taskDefinitions = Object.entries(template.Resources)
    .filter(([, resource]: any) => resource.Type === 'AWS::ECS::TaskDefinition') as [string, any][];
  const backendTask = taskDefinitions.find(([, task]) =>
    task.Properties.ContainerDefinitions[0].Name === 'backend')?.[0];
  const services = resources.filter(resource => resource.Type === 'AWS::ECS::Service');
  equal(services.length, 4);
  const backendService = services.find(service => service.Properties.TaskDefinition.Ref === backendTask);
  equal(backendService?.Properties.DesiredCount, 1);
  equal(services.filter(service => service !== backendService)
    .every(service => service.Properties.DesiredCount === 0), true);
  equal(resources.some(resource => resource.Type === 'AWS::ApplicationAutoScaling::ScalableTarget'), false);
  equal(template.Outputs.EcsDesiredCount.Value, '0');
});

test('P20 backend-only capacity override requires the isolated operation guard', () => {
  throws(() => synth({ backendDesiredCount: 1, p20AllowActivation: true }), /backendDesiredCount solo se permite/);
  throws(() => synth({
    backendDesiredCount: 1,
    backendMaxCapacity: 1,
    p20BackendOnlyOperation: true,
  }), /p20AllowActivation=true/);
  throws(() => synth({
    desiredCount: 1,
    backendDesiredCount: 1,
    backendMaxCapacity: 1,
    p20BackendOnlyOperation: true,
    p20AllowActivation: true,
  }), /capacidad global 0/);
  throws(() => synth({
    backendDesiredCount: 1,
    backendMaxCapacity: 2,
    p20BackendOnlyOperation: true,
    p20AllowActivation: true,
  }), /backendMaxCapacity=1/);
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
