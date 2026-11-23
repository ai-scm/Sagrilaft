import { deepStrictEqual, equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import {
  FILTRO_CORREO_FALLIDO,
  FILTRO_FIRMA_FALLIDA,
  UMBRAL_CONEXIONES_BASE_DATOS,
  UMBRAL_CPU_BASE_DATOS,
} from '../lib/constructs/observabilidad-alarmas';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'alarmas-test',
    proveedorListasCautela: 'deshabilitado',
    snsAlertasSub: 'pruebas@example.com',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON().Resources as Record<string, any>;
}

function alarmas(resources: Record<string, any>) {
  return Object.entries(resources)
    .filter(([, r]) => r.Type === 'AWS::CloudWatch::Alarm')
    .map(([id, r]) => ({ id, ...r.Properties }));
}

function alarma(resources: Record<string, any>, fragmentoId: string) {
  const encontradas = alarmas(resources).filter((a) => a.id.includes(fragmentoId));
  equal(encontradas.length, 1, `se esperaba una alarma con id ${fragmentoId}`);
  return encontradas[0];
}

const SERVICIOS = ['Backend', 'FormularioPublico', 'PortalInterno', 'Keycloak'];

// Al leer la plantilla desplegada, AWS cambia cada tilde por `?` y el preflight de
// deploy_release.py lo toma como un cambio no autorizado. Por eso todas las alarmas
// y filtros se escriben sin tildes.
const soloAscii = (texto: string) => /^[\x20-\x7E]*$/.test(texto);

for (const environment of ['staging', 'prod'] as const) {
  test(`${environment}: las alarmas y los filtros no llevan tildes ni caracteres especiales`, () => {
    const resources = synth(environment);
    for (const a of alarmas(resources)) {
      ok(soloAscii(a.AlarmDescription), `${a.id}: ${a.AlarmDescription}`);
    }
    const filtros = Object.entries(resources).filter(([, r]) => r.Type === 'AWS::Logs::MetricFilter');
    equal(filtros.length, 2);
    for (const [id, f] of filtros) ok(soloAscii(f.Properties.FilterPattern), `${id}: ${f.Properties.FilterPattern}`);
  });
}

for (const environment of ['staging', 'prod'] as const) {
  const resources = synth(environment);

  test(`${environment}: hay 3 alarmas originales + 8 de servicios + 3 de base de datos + 2 de operación`, () => {
    equal(alarmas(resources).length, 16);
  });

  test(`${environment}: las alarmas originales conservan su id (no se recrean)`, () => {
    for (const id of ['AlarmaErroresServidor', 'AlarmaSaturacionCpu', 'AlarmaSaturacionMemoria']) {
      alarma(resources, `AlarmasCriticas${id}`);
    }
  });

  for (const servicio of SERVICIOS) {
    test(`${environment}: ${servicio} avisa si se queda 3 minutos sin copias sanas`, () => {
      const a = alarma(resources, `AlarmaSinCopiasSanas${servicio}`);
      equal(a.MetricName, 'HealthyHostCount');
      equal(a.Statistic, 'Minimum');
      equal(a.Period, 60);
      equal(a.EvaluationPeriods, 3);
      equal(a.Threshold, 1);
      equal(a.ComparisonOperator, 'LessThanThreshold');
      equal(a.TreatMissingData, 'breaching');
      ok(a.Dimensions.some((d: any) => d.Name === 'TargetGroup'));
      ok(a.Dimensions.some((d: any) => d.Name === 'LoadBalancer'));
    });

    test(`${environment}: ${servicio} avisa si una copia falla 5 minutos seguidos`, () => {
      const a = alarma(resources, `AlarmaCopiasNoSanas${servicio}`);
      equal(a.MetricName, 'UnHealthyHostCount');
      equal(a.EvaluationPeriods, 5);
      equal(a.ComparisonOperator, 'GreaterThanOrEqualToThreshold');
    });
  }

  test(`${environment}: disco libre de la base de datos`, () => {
    const a = alarma(resources, 'AlarmaEspacioBaseDatos');
    equal(a.MetricName, 'FreeStorageSpace');
    equal(a.Namespace, 'AWS/RDS');
    equal(a.Threshold, (environment === 'prod' ? 10 : 2) * 1024 ** 3);
    equal(a.ComparisonOperator, 'LessThanThreshold');
  });

  test(`${environment}: CPU y conexiones de la base de datos`, () => {
    const cpu = alarma(resources, 'AlarmaCpuBaseDatos');
    equal(cpu.MetricName, 'CPUUtilization');
    equal(cpu.Namespace, 'AWS/RDS');
    equal(cpu.Threshold, UMBRAL_CPU_BASE_DATOS);
    equal(cpu.EvaluationPeriods, 3);
    const conexiones = alarma(resources, 'AlarmaConexionesBaseDatos');
    equal(conexiones.MetricName, 'DatabaseConnections');
    equal(conexiones.Threshold, UMBRAL_CONEXIONES_BASE_DATOS);
  });

  test(`${environment}: firma y correo fallidos salen de los registros del backend`, () => {
    const filtros = Object.values(resources).filter((r: any) => r.Type === 'AWS::Logs::MetricFilter');
    const porMetrica = Object.fromEntries(filtros.map((f: any) => [
      f.Properties.MetricTransformations[0].MetricName, f.Properties,
    ]));
    equal(porMetrica.FirmaZohoFallida.FilterPattern, FILTRO_FIRMA_FALLIDA);
    equal(porMetrica.CorreoContraparteFallido.FilterPattern, FILTRO_CORREO_FALLIDO);
    for (const f of Object.values(porMetrica) as any[]) {
      equal(f.MetricTransformations[0].MetricNamespace, `Sagrilaft/Operacion/${environment}`);
      equal(f.MetricTransformations[0].DefaultValue, 0);
      const grupo = resources[f.LogGroupName.Ref];
      equal(grupo.Properties.LogGroupName, `/sagrilaft/${environment}/ecs/backend`);
    }
    equal(alarma(resources, 'AlarmaFirmaFallida').MetricName, 'FirmaZohoFallida');
    equal(alarma(resources, 'AlarmaCorreoFallido').MetricName, 'CorreoContraparteFallido');
  });

  test(`${environment}: ${environment === 'prod' ? 'todas avisan por SNS al fallar y al recuperarse' : 'ninguna envía avisos'}`, () => {
    for (const a of alarmas(resources).filter((x) => x.id.startsWith('AlarmasCriticas'))) {
      if (environment === 'prod') {
        equal(a.AlarmActions?.length, 1, `${a.id} sin AlarmActions`);
        deepStrictEqual(a.OKActions, a.AlarmActions, `${a.id} sin OKActions`);
      } else {
        equal(a.AlarmActions, undefined, `${a.id} no debe avisar en staging`);
      }
    }
  });

  test(`${environment}: cada alarma nueva explica qué pasa en lenguaje llano`, () => {
    for (const a of alarmas(resources).filter((x) => x.id.startsWith('AlarmasCriticas'))) {
      const texto = JSON.stringify(a.AlarmDescription);
      ok(texto.length > 60, `${a.id} sin descripción útil`);
    }
  });
}
