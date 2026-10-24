import { deepStrictEqual, equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { SagrilaftStack } from '../lib/sagrilaft-stack';

function synth(environment: 'staging' | 'prod') {
  const app = new App({ context: {
    environment,
    imageTag: 'waf-admin-test',
    proveedorListasCautela: 'deshabilitado',
    snsAlertasSub: 'pruebas@example.com',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  return Template.fromStack(stack).toJSON();
}

function webAcl(environment: 'staging' | 'prod') {
  const resources = synth(environment).Resources as Record<string, any>;
  const acls = Object.values(resources).filter((r: any) => r.Type === 'AWS::WAFv2::WebACL');
  equal(acls.length, 1, 'debe existir exactamente un WebACL');
  return acls[0].Properties;
}

for (const environment of ['staging', 'prod'] as const) {
  test(`${environment}: la consola admin de Keycloak tiene límite propio de 200 por 5 min`, () => {
    const rule = webAcl(environment).Rules.find((r: any) => r.Name === 'LimiteTasaAdminKeycloak');
    ok(rule, 'falta la regla LimiteTasaAdminKeycloak');
    equal(rule.Statement.RateBasedStatement.Limit, 200);
    equal(rule.Statement.RateBasedStatement.AggregateKeyType, 'IP');
    equal(rule.Statement.RateBasedStatement.EvaluationWindowSec, 300);
    deepStrictEqual(rule.Action, { Block: {} });
  });

  test(`${environment}: el alcance de la regla cubre /admin y el POST de /realms/master`, () => {
    const rule = webAcl(environment).Rules.find((r: any) => r.Name === 'LimiteTasaAdminKeycloak');
    const scope = rule.Statement.RateBasedStatement.ScopeDownStatement;
    const statements = scope.OrStatement.Statements;
    const paths = statements.map((s: any) => [s.ByteMatchStatement.SearchString, s.ByteMatchStatement.PositionalConstraint]);
    deepStrictEqual(paths, [['/admin', 'STARTS_WITH'], ['/realms/master', 'STARTS_WITH']]);
    for (const s of statements) deepStrictEqual(s.ByteMatchStatement.FieldToMatch, { UriPath: {} });
  });

  test(`${environment}: las reglas existentes no cambian y las prioridades son únicas`, () => {
    const rules = webAcl(environment).Rules as any[];
    const byName = Object.fromEntries(rules.map((r) => [r.Name, r]));
    equal(byName.LimiteTasaGlobalPorIp.Statement.RateBasedStatement.Limit, 2000);
    equal(byName.LimiteTasaGlobalPorIp.Priority, 3);
    equal(byName.ProteccionVulnerabilidadesComunes.Priority, 1);
    equal(byName.BloqueoEntradasMaliciosasConocidas.Priority, 2);
    const priorities = rules.map((r) => r.Priority);
    equal(new Set(priorities).size, priorities.length, 'prioridades duplicadas');
  });
}
