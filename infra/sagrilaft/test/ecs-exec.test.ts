import { deepStrictEqual, equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

const ecsExecActions = [
  'ssmmessages:CreateControlChannel',
  'ssmmessages:CreateDataChannel',
  'ssmmessages:OpenControlChannel',
  'ssmmessages:OpenDataChannel',
].sort();

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'ecs-exec-test',
    proveedorListasCautela: 'deshabilitado',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON();
}

for (const environment of ['staging', 'prod'] as const) {
  test(`${environment}: backend ECS Exec permissions are attached to its task role`, () => {
    const resources = synth(environment).Resources as Record<string, any>;
    const backendTask = Object.values(resources).find((resource: any) =>
      resource.Type === 'AWS::ECS::TaskDefinition'
      && resource.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend')) as any;
    ok(backendTask);
    const backendTaskRole = backendTask.Properties.TaskRoleArn['Fn::GetAtt'][0];

    const backendRolePolicies = Object.values(resources).filter((resource: any) =>
      resource.Type === 'AWS::IAM::Policy'
      && resource.Properties.Roles.some((role: any) => role.Ref === backendTaskRole)) as any[];
    const actions = backendRolePolicies.flatMap((policy) =>
      policy.Properties.PolicyDocument.Statement.flatMap((statement: any) => {
        const statementActions = Array.isArray(statement.Action) ? statement.Action : [statement.Action];
        return statementActions.filter((action: string) => action.startsWith('ssmmessages:'));
      })).sort();
    deepStrictEqual(actions, ecsExecActions);

    const backendService = Object.values(resources).find((resource: any) =>
      resource.Type === 'AWS::ECS::Service'
      && resource.Properties.TaskDefinition.Ref === Object.entries(resources).find(([, task]: any) =>
        task.Type === 'AWS::ECS::TaskDefinition'
        && task.Properties.ContainerDefinitions.some((container: any) => container.Name === 'backend'))?.[0]) as any;
    equal(backendService?.Properties.EnableExecuteCommand, true);
  });
}
