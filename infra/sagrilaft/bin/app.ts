#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

const app = new cdk.App();
const environment = app.node.tryGetContext('environment') ?? 'prod';

new SagrilaftStack(app, `SagrilaftStack-${environment}`, {
  env: {
    account: app.node.tryGetContext('account') ?? process.env.CDK_DEFAULT_ACCOUNT,
    region: app.node.tryGetContext('region') ?? process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
  },
});

app.synth();
