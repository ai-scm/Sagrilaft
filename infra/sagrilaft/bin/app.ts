#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { SagrilaftStack } from '../lib/sagrilaft-stack';
import { DEFAULT_REGION, TARGET_ACCOUNT } from '../lib/deployment-constants';

const app = new cdk.App();
const environment = String(app.node.tryGetContext('environment') ?? 'prod');
const account = String(app.node.tryGetContext('account') ?? process.env.CDK_DEFAULT_ACCOUNT ?? '');
const region = String(app.node.tryGetContext('region') ?? process.env.CDK_DEFAULT_REGION ?? DEFAULT_REGION);
const protectedEnvironments = new Set(['staging', 'prod']);
const p20Environment = /^p20-[a-f0-9]{12}$/;

if (environment.startsWith('p20-') && !p20Environment.test(environment)) {
  throw new Error('Ambiente P20 inválido: use exactamente p20-<runId de 12 caracteres hexadecimales>.');
}

if (!protectedEnvironments.has(environment) && !p20Environment.test(environment) && environment !== 'dev') {
  throw new Error(`Ambiente no soportado: ${environment}.`);
}

if ((protectedEnvironments.has(environment) || p20Environment.test(environment)) && account !== TARGET_ACCOUNT) {
  throw new Error(
    `Cuenta AWS bloqueada para ${environment}: se recibio ${account || 'sin cuenta'}; ` +
    `la unica cuenta permitida es ${TARGET_ACCOUNT}. No usar la cuenta anterior.`,
  );
}


if (
  (protectedEnvironments.has(environment) || p20Environment.test(environment)) &&
  process.env.CDK_DEFAULT_ACCOUNT &&
  process.env.CDK_DEFAULT_ACCOUNT !== TARGET_ACCOUNT
) {
  throw new Error(
    `Credenciales AWS activas pertenecen a ${process.env.CDK_DEFAULT_ACCOUNT}; ` +
    `staging/prod solo pueden ejecutarse con ${TARGET_ACCOUNT}.`,
  );
}

new SagrilaftStack(app, `SagrilaftStack-${environment}`, {
  env: {
    account,
    region,
  },
});

app.synth();
