import { equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

const buildTimeOnlyKeys = [
  'VITE_PORTAL_INTERNO_URL',
  'VITE_KEYCLOAK_URL',
  'VITE_KEYCLOAK_REALM',
  'VITE_KEYCLOAK_CLIENT_ID',
];

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'build-time-config-test',
    proveedorListasCautela: 'deshabilitado',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON();
}

for (const environment of ['staging', 'prod'] as const) {
  test(`${environment}: Vite build-time values are not emitted as SSM runtime parameters`, () => {
    const resources = synth(environment).Resources as Record<string, any>;
    const parameters = Object.values(resources).filter((resource: any) =>
      resource.Type === 'AWS::SSM::Parameter') as any[];
    const parameterNames = parameters.map((parameter) => parameter.Properties.Name);
    const serializedResources = JSON.stringify(resources);

    for (const key of buildTimeOnlyKeys) {
      equal(parameterNames.includes(`/sagrilaft/${environment}/config/${key}`), false);
      equal(serializedResources.includes(`/sagrilaft/${environment}/config/${key}`), false);
      equal(serializedResources.includes(key), false);
    }

    // The backend's runtime Keycloak URL remains a real SSM-backed task secret.
    ok(parameterNames.includes(`/sagrilaft/${environment}/config/KEYCLOAK_URL`));
    const backendTask = Object.values(resources).find((resource: any) =>
      resource.Type === 'AWS::ECS::TaskDefinition'
      && resource.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend')) as any;
    const backend = backendTask.Properties.ContainerDefinitions.find(
      (container: any) => container.Name === 'backend',
    );
    ok(backend.Secrets.some((secret: any) => secret.Name === 'KEYCLOAK_URL'));
  });
}
