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

test('staging: habilitar dummy solo cambia el parámetro del proveedor y enciende el trabajador', () => {
  const before = synth('staging', 'deshabilitado');
  const after = synth('staging', 'dummy');
  const changed = Object.keys(after.Resources).filter(key =>
    JSON.stringify(before.Resources[key]) !== JSON.stringify(after.Resources[key]));
  equal(changed.length, 2);
  const parameterKey = changed.find(key => after.Resources[key].Type === 'AWS::SSM::Parameter')!;
  const workerKey = changed.find(key => after.Resources[key].Type === 'AWS::ECS::Service')!;
  const parameter = after.Resources[parameterKey];
  equal(parameter.Properties.Name, '/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA');
  equal(parameter.Properties.Value, 'dummy');
  equal(JSON.stringify(after.Resources[workerKey].Properties.TaskDefinition).includes('ListasWorkerTaskDefinition'), true);
  equal(before.Resources[workerKey].Properties.DesiredCount, 0);
  equal(after.Resources[workerKey].Properties.DesiredCount, 1);
  before.Resources[parameterKey].Properties.Value = 'dummy';
  before.Resources[workerKey].Properties.DesiredCount = 1;
  deepEqual(after, before);
});

test('comandos de staging usan el sandbox de Tusdatos y los de producción mantienen deshabilitado', () => {
  const { scripts } = JSON.parse(readFileSync(join(__dirname, '../package.json'), 'utf8'));
  for (const action of ['synth', 'diff', 'deploy', 'deploy:staging:bootstrap']) {
    const key = action.includes(':') ? action : `${action}:staging`;
    equal(scripts[key].includes('-c proveedorListasCautela=externo -c tusdatosUrl=http://docs.tusdatos.co'), true, key);
    equal(scripts[key].includes('-c habilitarNatEgress=true'), true, key);
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

test('producción: deshabilitado por defecto; admite Tusdatos real pero nunca el sandbox ni sin salida a Internet', () => {
  const base = { environment: 'prod', habilitarNatEgress: 'true' };
  equal(parametro(synthCon(base), '/sagrilaft/prod/config/PROVEEDOR_LISTAS_CAUTELA'), 'deshabilitado');
  const encendida = synthCon({ ...base, proveedorListasCautela: 'externo' });
  equal(parametro(encendida, '/sagrilaft/prod/config/PROVEEDOR_LISTAS_CAUTELA'), 'sagrilaft');
  equal(parametro(encendida, '/sagrilaft/prod/config/LISTAS_TUSDATOS_URL'), 'https://dash-board.tusdatos.co');
  throws(() => synthCon({ ...base, proveedorListasCautela: 'externo', tusdatosUrl: 'http://docs.tusdatos.co' }), /sandbox/);
  throws(() => synthCon({ environment: 'prod', proveedorListasCautela: 'externo' }), /habilitarNatEgress/);
  throws(() => synthCon({ ...base, proveedorListasCautela: 'deshabilitado', tusdatosUrl: 'http://docs.tusdatos.co' }), /sandbox/);
});

test('producción: encender Tusdatos solo cambia el parámetro del proveedor y enciende el trabajador', () => {
  const base = { environment: 'prod', habilitarNatEgress: 'true' };
  const antes = synthCon({ ...base, proveedorListasCautela: 'deshabilitado' });
  const despues = synthCon({ ...base, proveedorListasCautela: 'externo' });
  const cambiados = Object.keys(despues.Resources).filter(key =>
    JSON.stringify(antes.Resources[key]) !== JSON.stringify(despues.Resources[key]));
  deepEqual(cambiados.map(key => despues.Resources[key].Type).sort(), ['AWS::ECS::Service', 'AWS::SSM::Parameter']);
});

test('staging: pasar del simulador al sandbox de Tusdatos solo cambia dos parámetros', () => {
  const antes = synthCon({ proveedorListasCautela: 'dummy', habilitarNatEgress: 'true' });
  const despues = synthCon({ proveedorListasCautela: 'externo', habilitarNatEgress: 'true', tusdatosUrl: 'http://docs.tusdatos.co' });
  const cambiados = Object.keys(despues.Resources).filter(key =>
    JSON.stringify(antes.Resources[key]) !== JSON.stringify(despues.Resources[key]));
  deepEqual(cambiados.map(key => despues.Resources[key].Properties.Name).sort(), [
    '/sagrilaft/staging/config/LISTAS_TUSDATOS_URL',
    '/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA',
  ]);
  equal(parametro(despues, '/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA'), 'sagrilaft');
});
