import { deepEqual, equal, throws } from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod', zohoSignTesting?: string) {
  const app = new App({ context: {
    environment,
    proveedorListasCautela: environment === 'prod' ? 'deshabilitado' : 'dummy',
    imageTag: 'zoho-testing-test',
    snsAlertasSub: 'pruebas@example.com',
    ...(zohoSignTesting === undefined ? {} : { zohoSignTesting }),
  } });
  return Template.fromStack(new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  })).toJSON();
}

function parametro(plantilla: any, environment: string) {
  const [clave] = Object.keys(plantilla.Resources).filter(key => plantilla.Resources[key].Type === 'AWS::SSM::Parameter'
    && plantilla.Resources[key].Properties.Name === `/sagrilaft/${environment}/config/ZOHO_SIGN_TESTING`);
  return clave;
}

test('sin contexto: staging en prueba y producción real, como antes', () => {
  const staging = synth('staging');
  const prod = synth('prod');
  equal(staging.Resources[parametro(staging, 'staging')].Properties.Value, 'true');
  equal(prod.Resources[parametro(prod, 'prod')].Properties.Value, 'false');
});

test('producción con zohoSignTesting=true solo cambia ese parámetro', () => {
  const antes = synth('prod');
  const despues = synth('prod', 'true');
  const cambiados = Object.keys(despues.Resources).filter(key =>
    JSON.stringify(antes.Resources[key]) !== JSON.stringify(despues.Resources[key]));
  const clave = parametro(despues, 'prod');
  deepEqual(cambiados, [clave]);
  equal(despues.Resources[clave].Properties.Value, 'true');
});

test('valor inválido no sintetiza', () => {
  throws(() => synth('prod', 'si'), /zohoSignTesting invalido/);
});

test('los comandos de producción mantienen Zoho en prueba mientras se valida', () => {
  const { scripts } = JSON.parse(readFileSync(join(__dirname, '../package.json'), 'utf8'));
  for (const key of ['synth:prod', 'diff:prod', 'deploy:prod', 'deploy:prod:bootstrap']) {
    equal(scripts[key].includes('-c zohoSignTesting=true'), true, key);
  }
});
