import { deepEqual, equal, throws } from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod', proveedorListasCautela: string) {
  const app = new App({ context: {
    environment,
    proveedorListasCautela,
    imageTag: 'listas-cautela-test',
    snsAlertasSub: 'pruebas@example.com',
  } });
  return Template.fromStack(new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  })).toJSON();
}

test('staging: habilitar dummy solo cambia el valor del parámetro del proveedor', () => {
  const before = synth('staging', 'deshabilitado');
  const after = synth('staging', 'dummy');
  const changed = Object.keys(after.Resources).filter(key =>
    JSON.stringify(before.Resources[key]) !== JSON.stringify(after.Resources[key]));
  equal(changed.length, 1);
  const parameter = after.Resources[changed[0]];
  equal(parameter.Type, 'AWS::SSM::Parameter');
  equal(parameter.Properties.Name, '/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA');
  equal(parameter.Properties.Value, 'dummy');
  before.Resources[changed[0]].Properties.Value = 'dummy';
  deepEqual(after, before);
});

test('comandos de staging usan dummy y comandos de producción mantienen deshabilitado', () => {
  const { scripts } = JSON.parse(readFileSync(join(__dirname, '../package.json'), 'utf8'));
  for (const action of ['synth', 'diff', 'deploy', 'deploy:staging:bootstrap']) {
    const key = action.includes(':') ? action : `${action}:staging`;
    equal(scripts[key].includes('-c proveedorListasCautela=dummy'), true, key);
  }
  for (const key of ['synth:prod', 'diff:prod', 'deploy:prod', 'deploy:prod:bootstrap']) {
    equal(scripts[key].includes('-c proveedorListasCautela=deshabilitado'), true, key);
  }
});

test('producción conserva el parámetro deshabilitado y rechaza dummy', () => {
  const resources = Object.values(synth('prod', 'deshabilitado').Resources) as any[];
  const parameter = resources.find(resource => resource.Type === 'AWS::SSM::Parameter'
    && resource.Properties.Name === '/sagrilaft/prod/config/PROVEEDOR_LISTAS_CAUTELA');
  equal(parameter.Properties.Value, 'deshabilitado');
  throws(() => synth('prod', 'dummy'), /prod no permite.*dummy/);
});
