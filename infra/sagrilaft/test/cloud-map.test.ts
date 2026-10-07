import { deepStrictEqual, equal } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'cloud-map-test',
    proveedorListasCautela: 'deshabilitado',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON();
}

for (const environment of ['staging', 'prod'] as const) {
  test(`${environment}: only Keycloak is registered in the private Cloud Map namespace`, () => {
    const resources = synth(environment).Resources as Record<string, any>;
    const namespaceEntries = Object.entries(resources).filter(([, resource]) =>
      resource.Type === 'AWS::ServiceDiscovery::PrivateDnsNamespace');
    equal(namespaceEntries.length, 1);
    equal(namespaceEntries[0][1].Properties.Name, `sagrilaft-${environment}.local`);

    const cloudMapEntries = Object.entries(resources).filter(([, resource]) =>
      resource.Type === 'AWS::ServiceDiscovery::Service');
    equal(cloudMapEntries.length, 1);
    const [keycloakRegistryId, keycloakRegistry] = cloudMapEntries[0];
    equal(keycloakRegistry.Properties.Name, 'keycloak');
    deepStrictEqual(keycloakRegistry.Properties.NamespaceId, {
      'Fn::GetAtt': [namespaceEntries[0][0], 'Id'],
    });

    const ecsServices = Object.values(resources).filter((resource: any) =>
      resource.Type === 'AWS::ECS::Service') as any[];
    equal(ecsServices.length, 4);
    const serviceFamilies = ecsServices.map((service) =>
      resources[service.Properties.TaskDefinition.Ref].Properties.Family).sort();
    deepStrictEqual(serviceFamilies, [
      `sagrilaft-${environment}-backend`,
      `sagrilaft-${environment}-frontend`,
      `sagrilaft-${environment}-keycloak`,
      `sagrilaft-${environment}-portal`,
    ].sort());
    const servicesWithRegistry = ecsServices.filter((service) =>
      (service.Properties.ServiceRegistries ?? []).length > 0);
    equal(servicesWithRegistry.length, 1);
    deepStrictEqual(servicesWithRegistry[0].Properties.ServiceRegistries, [{
      RegistryArn: { 'Fn::GetAtt': [keycloakRegistryId, 'Arn'] },
    }]);

    const targetGroups = Object.values(resources).filter((resource: any) =>
      resource.Type === 'AWS::ElasticLoadBalancingV2::TargetGroup') as any[];
    equal(targetGroups.length, 4);
    deepStrictEqual(targetGroups.map((targetGroup) => targetGroup.Properties.Name).sort(), [
      `sagrilaft-${environment}-backend-ecs`,
      `sagrilaft-${environment}-frontend-ecs`,
      `sagrilaft-${environment}-keycloak-ecs`,
      `sagrilaft-${environment}-portal-ecs`,
    ].sort());

    const backendTask = Object.values(resources).find((resource: any) =>
      resource.Type === 'AWS::ECS::TaskDefinition'
      && resource.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend')) as any;
    const backendContainer = backendTask.Properties.ContainerDefinitions.find(
      (container: any) => container.Name === 'backend',
    );
    equal(
      backendContainer.Secrets.find((item: any) => item.Name === 'KEYCLOAK_URL') !== undefined,
      true,
    );
    const keycloakUrlParameter = Object.values(resources).find((resource: any) =>
      resource.Type === 'AWS::SSM::Parameter'
      && resource.Properties.Name === `/sagrilaft/${environment}/config/KEYCLOAK_URL`) as any;
    equal(
      keycloakUrlParameter.Properties.Value,
      `http://keycloak.sagrilaft-${environment}.local:8080`,
    );
  });
}
