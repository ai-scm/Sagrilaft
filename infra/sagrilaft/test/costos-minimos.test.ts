import { equal } from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

// Sistema mínimo: ver docs/produccion/ESTIMACION_COSTOS_AWS.md.
function synth(context: Record<string, string>) {
  const app = new App({ context: {
    imageTag: 'costos-test',
    snsAlertasSub: 'pruebas@example.com',
    ...context,
  } });
  return Template.fromStack(new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  })).toJSON();
}

const recursos = (plantilla: any, tipo: string) =>
  (Object.values(plantilla.Resources) as any[]).filter(r => r.Type === tipo);
const endpoints = (plantilla: any, tipo: 'Interface' | 'Gateway') =>
  recursos(plantilla, 'AWS::EC2::VPCEndpoint').filter(r => (r.Properties.VpcEndpointType ?? 'Gateway') === tipo);
const servicio = (plantilla: any, taskDef: string) =>
  recursos(plantilla, 'AWS::ECS::Service').find(r => JSON.stringify(r.Properties.TaskDefinition).includes(taskDef));

for (const environment of ['staging', 'prod']) {
  test(`${environment}: con NAT no se crean endpoints de interfaz; S3 conserva el gateway gratuito`, () => {
    const plantilla = synth({ environment, habilitarNatEgress: 'true' });
    equal(recursos(plantilla, 'AWS::EC2::NatGateway').length, 1);
    equal(endpoints(plantilla, 'Interface').length, 0);
    equal(endpoints(plantilla, 'Gateway').length, 1);
    const grupos = recursos(plantilla, 'AWS::EC2::SecurityGroup')
      .filter(r => r.Properties.GroupDescription === 'VPC endpoints para ECS Fargate sin NAT');
    equal(grupos.length, 0);
  });

  test(`${environment}: las tareas ECS heredan las etiquetas del servicio`, () => {
    const servicios = recursos(synth({ environment, habilitarNatEgress: 'true' }), 'AWS::ECS::Service');
    equal(servicios.length, 5);
    for (const s of servicios) equal(s.Properties.PropagateTags, 'SERVICE');
  });
}

test('sin NAT (red aislada) se mantienen los 9 endpoints de interfaz', () => {
  const plantilla = synth({ environment: 'staging', habilitarNatEgress: 'false' });
  equal(recursos(plantilla, 'AWS::EC2::NatGateway').length, 0);
  equal(endpoints(plantilla, 'Interface').length, 9);
});

test('por defecto los servicios sin autoescalado corren con una copia fija', () => {
  const plantilla = synth({ environment: 'prod', habilitarNatEgress: 'true' });
  for (const taskDef of ['KeycloakTaskDefinition', 'FrontendTaskDefinition', 'PortalTaskDefinition']) {
    equal(servicio(plantilla, taskDef).Properties.DesiredCount, 1, taskDef);
  }
});

for (const environment of ['staging', 'prod']) {
  test(`${environment}: CDK no fija las copias del backend cuando tiene autoescalado`, () => {
    // Si la plantilla fijara DesiredCount, cada despliegue bajaría el backend al
    // mínimo aunque el autoescalado lo hubiera subido por carga.
    const plantilla = synth({ environment, habilitarNatEgress: 'true' });
    equal('DesiredCount' in servicio(plantilla, 'BackendTaskDefinition').Properties, false);
    const [objetivo] = recursos(plantilla, 'AWS::ApplicationAutoScaling::ScalableTarget');
    equal(objetivo.Properties.MinCapacity, 1);
    equal(objetivo.Properties.MaxCapacity, 2);
  });
}

test('sin autoescalado el backend conserva su número fijo de copias', () => {
  // Bootstrap (0 copias) o máximo igual al mínimo: no hay quien decida el número.
  for (const [desiredCount, backendMaxCapacity] of [['0', '2'], ['1', '1']]) {
    const plantilla = synth({ environment: 'prod', habilitarNatEgress: 'true', desiredCount, backendMaxCapacity });
    equal(recursos(plantilla, 'AWS::ApplicationAutoScaling::ScalableTarget').length, 0);
    equal(servicio(plantilla, 'BackendTaskDefinition').Properties.DesiredCount, Number(desiredCount));
  }
});

test('el trabajador de listas no se enciende con las listas deshabilitadas', () => {
  const prod = synth({ environment: 'prod', habilitarNatEgress: 'true' });
  equal(servicio(prod, 'ListasWorkerTaskDefinition').Properties.DesiredCount, 0);
  const forzado = synth({ environment: 'prod', habilitarNatEgress: 'true', listasWorkerCount: '1' });
  equal(servicio(forzado, 'ListasWorkerTaskDefinition').Properties.DesiredCount, 1);
});

test('los comandos de staging y producción activan el NAT', () => {
  const { scripts } = JSON.parse(readFileSync(join(__dirname, '../package.json'), 'utf8'));
  for (const key of ['synth:staging', 'diff:staging', 'deploy:staging', 'deploy:staging:bootstrap',
    'synth:prod', 'diff:prod', 'deploy:prod', 'deploy:prod:bootstrap']) {
    equal(scripts[key].includes('-c habilitarNatEgress=true'), true, key);
  }
});

test('el backend escala de 1 a 2 copias como máximo', () => {
  const plantilla = synth({ environment: 'prod', habilitarNatEgress: 'true' });
  const objetivos = recursos(plantilla, 'AWS::ApplicationAutoScaling::ScalableTarget');
  equal(objetivos.length, 1);
  equal(objetivos[0].Properties.MinCapacity, 1);
  equal(objetivos[0].Properties.MaxCapacity, 2);
});

test('disco de la base: producción 100 GB; staging 20 GB gp3 en una instancia nueva', () => {
  const prod = recursos(synth({ environment: 'prod', habilitarNatEgress: 'true' }), 'AWS::RDS::DBInstance');
  equal(prod.length, 1);
  equal(prod[0].Properties.AllocatedStorage, '100');
  equal(prod[0].Properties.MaxAllocatedStorage, undefined);
  const plantillaStaging = synth({ environment: 'staging', habilitarNatEgress: 'true' });
  const staging = recursos(plantillaStaging, 'AWS::RDS::DBInstance');
  equal(staging.length, 1);
  equal(staging[0].Properties.AllocatedStorage, '20');
  equal(staging[0].Properties.MaxAllocatedStorage, 50);
  equal(staging[0].Properties.StorageType, 'gp3');
  equal(staging[0].DeletionPolicy, 'Retain');
  const idStaging = Object.keys(plantillaStaging.Resources)
    .find(k => plantillaStaging.Resources[k].Type === 'AWS::RDS::DBInstance')!;
  equal(idStaging.startsWith('DatabasePostgresDisco20'), true);
});
