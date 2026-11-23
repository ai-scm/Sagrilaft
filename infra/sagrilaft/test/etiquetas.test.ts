import { deepEqual, equal, ok } from 'node:assert/strict';
import { test } from 'node:test';
import { App, CfnResource, Stack, TagManager } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { COMPONENTES } from '../lib/etiquetas';
import { SagrilaftStack } from '../lib/sagrilaft-stack';

// Contexto equivalente al de staging/prod: certificado, zona DNS e identidad SES
// importados (compartidos con otros proyectos), NAT activo.
function synth(environment: string) {
  const app = new App({ context: {
    environment,
    imageTag: 'etiquetas-test',
    snsAlertasSub: 'pruebas@example.com',
    hostedZoneName: 'ia.blend360.com',
    hostedZoneId: 'Z000000000TEST',
    certificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000',
    habilitarNatEgress: 'true',
    zohoSecretYaExiste: environment === 'prod' ? 'true' : 'false',
  } });
  const stack = new SagrilaftStack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });
  // Sintetizar antes de recorrer el árbol: algunas políticas IAM se generan en la síntesis.
  const recursos = Template.fromStack(stack).toJSON().Resources as Record<string, any>;
  return { stack, recursos };
}

// CloudFormation usa lista [{Key, Value}] en casi todos los tipos y mapa en SSM.
function etiquetas(recurso: any): Record<string, string> {
  const tags = recurso.Properties?.Tags;
  if (!tags) return {};
  if (Array.isArray(tags)) return Object.fromEntries(tags.map((t: any) => [t.Key, t.Value]));
  return tags;
}

/** Recursos del stack separados según CDK los considere etiquetables o no. */
function clasificar(stack: Stack) {
  const cfn = stack.node.findAll().filter(CfnResource.isCfnResource) as CfnResource[];
  const id = (r: CfnResource) => stack.resolve(r.logicalId) as string;
  const etiquetable = (r: CfnResource) => TagManager.isTaggable(r) || TagManager.isTaggableV2(r);
  return {
    etiquetables: cfn.filter(etiquetable).map(r => ({ id: id(r), tipo: r.cfnResourceType })),
    noEtiquetables: cfn.filter(r => !etiquetable(r) && r.cfnResourceType !== 'AWS::CDK::Metadata')
      .map(r => ({ id: id(r), tipo: r.cfnResourceType })),
  };
}

// Tipos que no admiten etiquetas en la plantilla. Algunos (listeners, sus reglas y
// el ScalableTarget) reciben igual las etiquetas del stack que CloudFormation les
// copia al desplegar, pero nunca Component. Si aparece un tipo nuevo, esta lista
// obliga a revisar si de verdad no admite etiquetas antes de aceptarlo.
const TIPOS_NO_ETIQUETABLES = [
  'AWS::ApplicationAutoScaling::ScalableTarget',
  'AWS::ApplicationAutoScaling::ScalingPolicy',
  'AWS::EC2::Route',
  'AWS::EC2::SecurityGroupIngress',
  'AWS::EC2::SubnetRouteTableAssociation',
  'AWS::EC2::VPCGatewayAttachment',
  'AWS::ElasticLoadBalancingV2::Listener',
  'AWS::ElasticLoadBalancingV2::ListenerRule',
  'AWS::IAM::ManagedPolicy',
  'AWS::IAM::Policy',
  'AWS::Route53::RecordSet',
  // Política del bucket de registros de acceso del ALB (permiso de escritura del
  // ALB y exigencia de TLS). El tipo no tiene propiedad Tags en CloudFormation.
  'AWS::S3::BucketPolicy',
  'AWS::SNS::Subscription',
  'AWS::SecretsManager::SecretTargetAttachment',
  'AWS::WAFv2::WebACLAssociation',
];

// Recursos compartidos con otros proyectos de la cuenta: el stack los importa y
// nunca debe crearlos (crearlos los convertiría en recursos de SAGRILAFT).
const TIPOS_COMPARTIDOS = [
  'AWS::CertificateManager::Certificate',
  'AWS::Route53::HostedZone',
  'AWS::SES::EmailIdentity',
  'AWS::SES::ConfigurationSet',
  'AWS::IAM::OIDCProvider',
  'Custom::AWSCDKOpenIdConnectProvider',
  'AWS::IAM::User',
  'AWS::IAM::Group',
];

for (const environment of ['staging', 'prod']) {
  const { stack, recursos } = synth(environment);
  const { etiquetables, noEtiquetables } = clasificar(stack);

  test(`${environment}: todo recurso que admite etiquetas lleva las cuatro, sin depender de Project`, () => {
    ok(etiquetables.length > 100, `se esperaban más de 100 recursos etiquetables, hay ${etiquetables.length}`);
    for (const { id, tipo } of etiquetables) {
      const t = etiquetas(recursos[id]);
      const contexto = `${id} (${tipo}) tiene ${JSON.stringify(t)}`;
      equal(t.Project, 'sagrilaft', contexto);
      equal(t.Environment, environment, contexto);
      equal(t.ManagedBy, 'cdk', contexto);
      ok((COMPONENTES as readonly string[]).includes(t.Component), contexto);
    }
  });

  test(`${environment}: solo quedan sin etiquetas los tipos que CloudFormation no permite etiquetar`, () => {
    const tipos = [...new Set(noEtiquetables.map(r => r.tipo))];
    for (const tipo of tipos) ok(TIPOS_NO_ETIQUETABLES.includes(tipo), `tipo sin etiquetas no previsto: ${tipo}`);
    for (const { id } of noEtiquetables) deepEqual(etiquetas(recursos[id]), {}, id);
  });

  test(`${environment}: la plantilla no tiene recursos fuera del inventario`, () => {
    const enArbol = new Set([...etiquetables, ...noEtiquetables].map(r => r.id));
    const sueltos = Object.entries(recursos)
      .filter(([id, r]) => r.Type !== 'AWS::CDK::Metadata' && !enArbol.has(id))
      .map(([id, r]) => `${id} (${r.Type})`);
    deepEqual(sueltos, []);
  });

  test(`${environment}: no crea ni etiqueta recursos compartidos con otros proyectos`, () => {
    const compartidos = Object.entries(recursos)
      .filter(([, r]) => TIPOS_COMPARTIDOS.includes(r.Type))
      .map(([id, r]) => `${id} (${r.Type})`);
    deepEqual(compartidos, [], 'certificado, zona DNS, identidad SES y credenciales de CI se importan, no se crean');
    // Los únicos roles del stack son los de las tareas ECS; los roles de CI y de
    // bootstrap de CDK son compartidos y viven fuera de este stack.
    const roles = Object.values(recursos).filter((r: any) => r.Type === 'AWS::IAM::Role');
    equal(roles.length, 6);
    for (const r of roles) {
      const principales = JSON.stringify(r.Properties.AssumeRolePolicyDocument.Statement.map((s: any) => s.Principal));
      equal(principales, JSON.stringify([{ Service: 'ecs-tasks.amazonaws.com' }]));
    }
    // Los registros DNS van en la zona importada (no etiquetable desde el registro).
    for (const r of Object.values(recursos).filter((x: any) => x.Type === 'AWS::Route53::RecordSet')) {
      equal((r as any).Properties.HostedZoneId, 'Z000000000TEST');
    }
  });

  test(`${environment}: cada bloque recibe su componente`, () => {
    const esperado: Record<string, string> = {
      Networking: 'red',
      Storage: 'almacenamiento',
      Secrets: 'secretos',
      Notifications: 'notificaciones',
      ConfigParameters: 'configuracion',
      Database: 'base-datos',
      Lb: 'balanceador',
      CortafuegosWeb: 'cortafuegos-web',
      AlarmasCriticas: 'observabilidad',
      DashboardTecnico: 'observabilidad',
      DashboardNegocio: 'observabilidad',
      EcsFargateCluster: 'plataforma-contenedores',
      EcsFargateTaskExecutionRole: 'plataforma-contenedores',
      EcsFargateBackend: 'backend',
      EcsFargateFrontend: 'formulario-publico',
      EcsFargatePortal: 'portal-interno',
      EcsFargateKeycloak: 'keycloak',
      EcsFargateListasWorker: 'listas-worker',
      EcsFargateMigration: 'migraciones',
      EcrBackendRepo: 'backend',
      EcrFormularioPublicoRepo: 'formulario-publico',
      EcrPortalInternoRepo: 'portal-interno',
      EcrKeycloakRepo: 'keycloak',
    };
    for (const [prefijo, componente] of Object.entries(esperado)) {
      const valores = [...new Set(etiquetables.filter(r => r.id.startsWith(prefijo))
        .map(r => etiquetas(recursos[r.id]).Component))];
      deepEqual(valores, [componente], prefijo);
    }
  });

  test(`${environment}: los servicios ECS siguen propagando sus etiquetas a las tareas`, () => {
    const servicios = Object.values(recursos).filter((r: any) => r.Type === 'AWS::ECS::Service');
    equal(servicios.length, 5);
    for (const s of servicios) equal(s.Properties.PropagateTags, 'SERVICE');
  });
}
