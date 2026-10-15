import { deepStrictEqual, equal, throws } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

const environment = 'p20-9c67b6ea6842';
const cert = 'arn:aws:acm:us-east-1:874641912777:certificate/11111111-1111-1111-1111-111111111111';
const browserCert = 'arn:aws:acm:us-east-1:874641912777:certificate/22222222-2222-2222-2222-222222222222';
const host = 'p20-9c67b6ea6842-c7-test-20261012.cbm5sq1kjl57.us-east-1.rds.amazonaws.com';
function synth(context: Record<string, unknown> = {}) {
  const app = new App({ context: { environment, certificateArn: cert, hostedZoneName: '', hostedZoneId: '',
    imageTag: 'ff0061a39166c549084e1a55769c172104eac86b',
    backendImageTag: '4d63c1356cc92b8d8d515e7147a7ac06565b0583',
    migrationImageTag: '0d6ee0633f516f8ae5b8d4354661ae583166977e',
    databaseHostOverride: host, restoredDbIdentifier: 'p20-9c67b6ea6842-c7-test-20261012',
    desiredCount: 1, p20AllowActivation: true,
    backendMaxCapacity: 1, ...context } });
  return Template.fromStack(new SagrilaftStack(app, 'P20TestStack', {
    env: { account: '874641912777', region: 'us-east-1' },
  })).toJSON();
}
const browser = { p20PrivateBrowserAccess: true, p20BrowserCertificateArn: browserCert };

test('private browser changes only origins, host routing, imported TLS and domain output', () => {
  const before = synth(), after = synth(browser);
  const expectedParams: Record<string, string> = {
    FRONTEND_URL: `https://formulario.${environment}.invalid,https://portal.${environment}.invalid`,
    PORTAL_INTERNO_URL: `https://portal.${environment}.invalid`,
    KEYCLOAK_HOSTNAME: `login.${environment}.invalid`,
    KEYCLOAK_ISSUER_URL: `https://login.${environment}.invalid`,
    ZOHO_REDIRECT_URI: `https://portal.${environment}.invalid/oauth/zoho/callback`,
  };
  let params = 0, rules = 0, buckets = 0, listeners = 0;
  for (const [id, resource] of Object.entries(after.Resources) as [string, any][]) {
    const old = before.Resources[id], props = resource.Properties;
    if (JSON.stringify(resource) === JSON.stringify(old)) continue;
    if (resource.Type === 'AWS::SSM::Parameter') {
      equal(props.Value, expectedParams[props.Name.split('/').pop()]);
      props.Value = old.Properties.Value; params++;
    } else if (resource.Type === 'AWS::S3::Bucket') {
      equal(props.CorsConfiguration.CorsRules[0].AllowedOrigins[0], `https://portal.${environment}.invalid`);
      props.CorsConfiguration.CorsRules[0].AllowedOrigins[0] = old.Properties.CorsConfiguration.CorsRules[0].AllowedOrigins[0];
      buckets++;
    } else if (resource.Type === 'AWS::ElasticLoadBalancingV2::ListenerRule') {
      const condition = props.Conditions.find((x: any) => x.Field === 'host-header');
      equal(condition.HostHeaderConfig.Values.length, 1);
      equal(['formulario', 'portal', 'login'].map(x => `${x}.${environment}.invalid`).includes(condition.HostHeaderConfig.Values[0]), true);
      props.Conditions = old.Properties.Conditions; rules++;
    } else if (resource.Type === 'AWS::ElasticLoadBalancingV2::Listener') {
      deepStrictEqual(props.Certificates, [{ CertificateArn: browserCert }]);
      props.Certificates = old.Properties.Certificates; listeners++;
    } else throw new Error(`Unexpected resource change: ${id}`);
    deepStrictEqual(resource, old);
  }
  equal(params, 5); equal(rules, 5); equal(buckets, 1); equal(listeners, 1);
  equal(after.Outputs.EcsDatabaseHost.Value, host);
  equal(after.Outputs.DominiosEsperados.Value,
    `formulario.${environment}.invalid, portal.${environment}.invalid, login.${environment}.invalid`);
  after.Outputs.DominiosEsperados.Value = before.Outputs.DominiosEsperados.Value;
  // Compare the entire template: images, tasks, capacity, DB, IAM and network.
  deepStrictEqual(after, before);
});

test('private browser rejects shared URLs, missing/reused/foreign certificates and non-P20', () => {
  throws(() => synth({ p20PrivateBrowserAccess: true }), /certificado ACM dedicado/);
  throws(() => synth({ ...browser, p20BrowserCertificateArn: cert }), /certificado ACM dedicado/);
  for (const arn of [browserCert.replace('us-east-1', 'us-west-2'), browserCert.replace('874641912777', '123456789012')]) {
    throws(() => synth({ ...browser, p20BrowserCertificateArn: arn }), /certificado ACM dedicado/);
  }
  for (const key of ['domainName', 'portalDomainName', 'keycloakDomainName']) {
    throws(() => synth({ ...browser, [key]: 'shared.example.com' }), /origen exclusivo/);
  }
  for (const env of ['staging', 'prod', 'dev']) {
    throws(() => synth({ ...browser, environment: env }), /solo se permite en P20/);
  }
  throws(() => synth({ p20BrowserCertificateArn: browserCert }), /requiere p20PrivateBrowserAccess/);
  throws(() => synth({ p20PrivateBrowserAccess: 'yes' }), /debe ser true o false/);
  for (const context of [
    { databaseHostOverride: '' },
    { databaseHostOverride: 'staging.us-east-1.rds.amazonaws.com' },
    { restoredDbIdentifier: 'p20-9c67b6ea6842-restore-20261009c' },
    { restoredDbIdentifier: 'p20-012345abcdef-c7-test-20261012' },
    { databaseHostOverride: host.replace('us-east-1', 'us-west-2') },
  ]) throws(() => synth({ ...browser, ...context }), /RDS clonada c7-test/);
});

test('omitting private browser mode preserves existing synthesis', () => {
  deepStrictEqual(synth(), synth({ p20PrivateBrowserAccess: false }));
});
