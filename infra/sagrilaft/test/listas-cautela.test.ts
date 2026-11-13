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

// ── Fase 7: modalidad externa, trabajador y custodia en staging ─────────────

function synthCon(context: Record<string, string>) {
  const app = new App({ context: {
    environment: 'staging', imageTag: 'listas-cautela-test', snsAlertasSub: 'pruebas@example.com', ...context,
  } });
  return Template.fromStack(new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  })).toJSON();
}

function parametro(plantilla: any, nombre: string): string | undefined {
  const recurso = (Object.values(plantilla.Resources) as any[]).find(r => r.Type === 'AWS::SSM::Parameter'
    && r.Properties.Name === nombre);
  return recurso?.Properties.Value;
}

function contenedor(plantilla: any, familia: string): any {
  const definicion = (Object.values(plantilla.Resources) as any[]).find(r => r.Type === 'AWS::ECS::TaskDefinition'
    && r.Properties.Family === familia);
  return definicion?.Properties.ContainerDefinitions[0];
}

test('staging: el trabajador de listas corre como servicio y usa la custodia en S3', () => {
  const plantilla = synthCon({ proveedorListasCautela: 'dummy' });
  const trabajador = contenedor(plantilla, 'sagrilaft-staging-listas-worker');
  equal(JSON.stringify(trabajador.Command).includes('python -m infrastructure.listas.trabajador_servicio'), true);
  equal(trabajador.PortMappings, undefined);
  const servicio = (Object.values(plantilla.Resources) as any[]).find(r => r.Type === 'AWS::ECS::Service'
    && JSON.stringify(r.Properties.TaskDefinition).includes('ListasWorkerTaskDefinition'));
  equal(servicio.Properties.DesiredCount, 1);
  equal(servicio.Properties.LoadBalancers, undefined);
  equal(parametro(plantilla, '/sagrilaft/staging/config/LISTAS_CUSTODIA_BACKEND'), 's3');
  equal(parametro(plantilla, '/sagrilaft/staging/config/LISTAS_CUSTODIA_S3_PREFIJO'), 'listas/custodia/');
  for (const familia of ['sagrilaft-staging-backend', 'sagrilaft-staging-listas-worker']) {
    const nombres = contenedor(plantilla, familia).Secrets.map((s: any) => s.Name);
    for (const variable of ['LISTAS_CUSTODIA_BACKEND', 'LISTAS_TUSDATOS_URL', 'LISTAS_TUSDATOS_TOKEN',
      'LISTAS_TUSDATOS_USUARIO', 'LISTAS_TUSDATOS_CLAVE', 'PROVEEDOR_LISTAS_CAUTELA']) {
      equal(nombres.includes(variable), true, `${familia}: ${variable}`);
    }
  }
});

test('el bootstrap no levanta el trabajador', () => {
  const servicio = (Object.values(synthCon({ proveedorListasCautela: 'dummy', desiredCount: '0' }).Resources) as any[])
    .find(r => r.Type === 'AWS::ECS::Service' && JSON.stringify(r.Properties.TaskDefinition).includes('ListasWorkerTaskDefinition'));
  equal(servicio.Properties.DesiredCount, 0);
});

test('staging: la modalidad externa exige salida a Internet y usa el secreto de Tusdatos', () => {
  throws(() => synthCon({ proveedorListasCautela: 'externo' }), /habilitarNatEgress/);
  const plantilla = synthCon({ proveedorListasCautela: 'externo', habilitarNatEgress: 'true' });
  equal(parametro(plantilla, '/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA'), 'sagrilaft');
  equal(parametro(plantilla, '/sagrilaft/staging/config/LISTAS_TUSDATOS_URL'), 'https://dash-board.tusdatos.co');
  const secreto = (Object.values(plantilla.Resources) as any[]).find(r => r.Type === 'AWS::SecretsManager::Secret'
    && r.Properties.Name === 'sagrilaft/staging/tusdatos_credentials');
  deepEqual(JSON.parse(secreto.Properties.SecretString), { token: '', usuario: '', clave: '' });
  const sandbox = synthCon({ proveedorListasCautela: 'externo', habilitarNatEgress: 'true', tusdatosUrl: 'http://docs.tusdatos.co' });
  equal(parametro(sandbox, '/sagrilaft/staging/config/LISTAS_TUSDATOS_URL'), 'http://docs.tusdatos.co');
});

test('URL de Tusdatos inválida o modalidad desconocida no sintetizan', () => {
  throws(() => synthCon({ proveedorListasCautela: 'dummy', tusdatosUrl: 'http://dash-board.tusdatos.co' }), /tusdatosUrl/);
  throws(() => synthCon({ proveedorListasCautela: 'dummy', tusdatosUrl: 'https://dash-board.tusdatos.co/api' }), /tusdatosUrl/);
  throws(() => synthCon({ proveedorListasCautela: 'tusdatos' }), /desconocido/);
});

test('producción: deshabilitado por defecto y rechaza la modalidad externa y el sandbox', () => {
  const base = { environment: 'prod', habilitarNatEgress: 'true' };
  equal(parametro(synthCon(base), '/sagrilaft/prod/config/PROVEEDOR_LISTAS_CAUTELA'), 'deshabilitado');
  throws(() => synthCon({ ...base, proveedorListasCautela: 'externo' }), /prod mantiene las listas deshabilitadas/);
  throws(() => synthCon({ ...base, proveedorListasCautela: 'sagrilaft' }), /prod mantiene las listas deshabilitadas/);
  throws(() => synthCon({ ...base, proveedorListasCautela: 'deshabilitado', tusdatosUrl: 'http://docs.tusdatos.co' }), /sandbox/);
});
