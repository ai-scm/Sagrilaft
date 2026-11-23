import { deepStrictEqual, equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { DIAS_RETENCION_REGISTROS_ACCESO, PREFIJO_REGISTROS_ACCESO } from '../lib/constructs/load-balancer';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'ip-cliente-test',
    proveedorListasCautela: 'deshabilitado',
    snsAlertasSub: 'pruebas@example.com',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON().Resources as Record<string, any>;
}

function porTipo(resources: Record<string, any>, tipo: string) {
  return Object.entries(resources).filter(([, r]) => r.Type === tipo);
}

for (const environment of ['staging', 'prod'] as const) {
  const resources = synth(environment);

  test(`${environment}: TRUSTED_PROXY_IPS es el CIDR de la VPC, no 172.0.0.0/8`, () => {
    const [[, param]] = porTipo(resources, 'AWS::SSM::Parameter')
      .filter(([, r]) => r.Properties.Name === `/sagrilaft/${environment}/config/TRUSTED_PROXY_IPS`);
    const [[vpcId]] = porTipo(resources, 'AWS::EC2::VPC');
    deepStrictEqual(param.Properties.Value, { 'Fn::GetAtt': [vpcId, 'CidrBlock'] });
  });

  test(`${environment}: el ALB guarda registros de acceso en un bucket propio`, () => {
    const [[, alb]] = porTipo(resources, 'AWS::ElasticLoadBalancingV2::LoadBalancer');
    const atributos = Object.fromEntries(
      alb.Properties.LoadBalancerAttributes.map((a: any) => [a.Key, a.Value]),
    );
    equal(atributos['access_logs.s3.enabled'], 'true');
    equal(atributos['access_logs.s3.prefix'], PREFIJO_REGISTROS_ACCESO);
    const bucketRef = atributos['access_logs.s3.bucket'];
    ok(bucketRef?.Ref, 'el bucket de registros debe ser un recurso del stack');

    const bucket = resources[bucketRef.Ref];
    equal(bucket.Type, 'AWS::S3::Bucket');
    equal(bucket.DeletionPolicy, 'Retain');
    equal(
      bucket.Properties.BucketEncryption.ServerSideEncryptionConfiguration[0]
        .ServerSideEncryptionByDefault.SSEAlgorithm,
      'AES256',
    );
    deepStrictEqual(bucket.Properties.PublicAccessBlockConfiguration, {
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    });
    const [regla] = bucket.Properties.LifecycleConfiguration.Rules;
    equal(regla.ExpirationInDays, DIAS_RETENCION_REGISTROS_ACCESO);
    equal(regla.Status, 'Enabled');
  });

  test(`${environment}: el bucket de registros es distinto al de documentos`, () => {
    const buckets = porTipo(resources, 'AWS::S3::Bucket');
    equal(buckets.length, 2);
  });

  test(`${environment}: el bucket de registros lleva Component=balanceador`, () => {
    const [[, alb]] = porTipo(resources, 'AWS::ElasticLoadBalancingV2::LoadBalancer');
    const bucketId = alb.Properties.LoadBalancerAttributes
      .find((a: any) => a.Key === 'access_logs.s3.bucket').Value.Ref;
    const tags = Object.fromEntries(
      resources[bucketId].Properties.Tags.map((t: any) => [t.Key, t.Value]),
    );
    equal(tags.Component, 'balanceador');
    equal(tags.Project, 'sagrilaft');
  });
}
