import * as cdk from 'aws-cdk-lib';
import { CfnOutput } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

import { Networking } from './constructs/networking';
import { Storage } from './constructs/storage';
import { Secrets } from './constructs/secrets';
import { Notifications } from './constructs/notifications';
import { Observability } from './constructs/observability';
import { Database } from './constructs/database';
import { Compute } from './constructs/compute';
import { LoadBalancer } from './constructs/load-balancer';

// ─────────────────────────────────────────────────────────────────────────────
// TODO: Reemplazar los 3 dominios cuando se compren.
//
//   Formulario público : DEFAULT_DOMINIO          (ej: sagrilaft.miempresa.com)
//   Portal interno     : DEFAULT_DOMINIO_PORTAL    (ej: portal.miempresa.com)
//   Autenticación      : DEFAULT_DOMINIO_KEYCLOAK  (ej: auth.miempresa.com)
//
// Para desplegar con los dominios reales:
//   npx cdk deploy \
//     -c domainName=sagrilaft.miempresa.com \
//     -c portalDomainName=portal.miempresa.com \
//     -c keycloakDomainName=auth.miempresa.com \
//     -c sesEmailOrigen=alertas@miempresa.com \
//     -c snsAlertasSub=equipo-analistas@miempresa.com
// ─────────────────────────────────────────────────────────────────────────────
const DEFAULT_DOMINIO          = 'sagrilaft.tudominio.com';   // TODO: reemplazar
const DEFAULT_DOMINIO_PORTAL   = 'portal.tudominio.com';      // TODO: reemplazar
const DEFAULT_DOMINIO_KEYCLOAK = 'auth.tudominio.com';        // TODO: reemplazar

export class SagrilaftStack extends cdk.Stack {
  constructor(scope: Construct, constructId: string, props?: cdk.StackProps) {
    super(scope, constructId, props);

    // ── Parámetros de contexto ─────────────────────────────────────────────
    const ambiente        = String(this.node.tryGetContext('environment')       ?? 'prod');
    const dominio         = String(this.node.tryGetContext('domainName')        ?? DEFAULT_DOMINIO);
    const dominioPortal   = String(this.node.tryGetContext('portalDomainName')  ?? DEFAULT_DOMINIO_PORTAL);
    const dominioKeycloak = String(this.node.tryGetContext('keycloakDomainName')?? DEFAULT_DOMINIO_KEYCLOAK);
    const certArn         = String(this.node.tryGetContext('certificateArn')    ?? '');
    const sesEmailOrigen  = String(this.node.tryGetContext('sesEmailOrigen')    ?? 'alertas@sagrilaft.com');
    const snsAlertasSub   = String(this.node.tryGetContext('snsAlertasSub')     ?? 'equipo-analistas@sagrilaft.com');

    cdk.Tags.of(this).add('Project', 'sagrilaft');
    cdk.Tags.of(this).add('Environment', ambiente);

    // ── Constructs ─────────────────────────────────────────────────────────
    const networking    = new Networking(this, 'Networking');
    const storage       = new Storage(this, 'Storage');
    const secrets       = new Secrets(this, 'Secrets', { ambiente });
    const notifications = new Notifications(this, 'Notifications', { ambiente, sesEmailOrigen, snsAlertasSub });
    const observability = new Observability(this, 'Observability', { ambiente });

    const database = new Database(this, 'Database', {
      vpc: networking.vpc,
      securityGroup: networking.sgRds,
      credentialsSecret: secrets.dbSecret,
    });

    const compute = new Compute(this, 'Compute', {
      vpc: networking.vpc,
      securityGroup: networking.sgEc2,
      bucket: storage.bucket,
      db: database.instance,
      dbSecret: secrets.dbSecret,
      alertasTopic: notifications.alertasTopic,
      sesEmailOrigen,
      logGroupArns: observability.allLogGroupArns,
      lgBootstrap: observability.lgBootstrap,
      lgBackend: observability.lgBackend,
      lgFrontend: observability.lgFrontend,
      lgPortal: observability.lgPortal,
      lgKeycloak: observability.lgKeycloak,
      grantSecretsRead: (grantee) => secrets.grantReadAll(grantee),
    });

    const certificado = certArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', certArn)
      : new acm.Certificate(this, 'Cert', {
        domainName: dominio,
        subjectAlternativeNames: [dominioPortal, dominioKeycloak],
        validation: acm.CertificateValidation.fromDns(),
      });

    const lb = new LoadBalancer(this, 'Lb', {
      vpc: networking.vpc,
      securityGroup: networking.sgAlb,
      ec2Instance: compute.instance,
      certificado,
      dominioPortal,
      dominioKeycloak,
    });

    // ── Outputs ────────────────────────────────────────────────────────────
    new CfnOutput(this, 'AlbDns',            { value: lb.alb.loadBalancerDnsName, description: 'Apunta tus dominios a este CNAME en Route 53 o tu DNS' });
    new CfnOutput(this, 'DominiosEsperados', { value: `${dominio}, ${dominioPortal}, ${dominioKeycloak}`, description: 'Hostnames que deben apuntar al ALB' });
    new CfnOutput(this, 'S3Bucket',          { value: storage.bucket.bucketName, description: 'Nombre del bucket S3 para uploads' });
    new CfnOutput(this, 'RdsEndpoint',       { value: database.instance.dbInstanceEndpointAddress, description: 'Host RDS PostgreSQL' });
    new CfnOutput(this, 'KeycloakDbName',    { value: 'keycloak', description: 'Base de datos separada que usa Keycloak en la misma instancia RDS' });
    new CfnOutput(this, 'Ec2InstanceId',     { value: compute.instance.instanceId, description: 'ID de la instancia EC2 (para SSM Session Manager)' });
    new CfnOutput(this, 'DbSecretArn',       { value: secrets.dbSecret.secretArn, description: 'ARN del secreto con la contrasena de la BD' });
    new CfnOutput(this, 'SnsAlertasTopicArn',{ value: notifications.alertasTopic.topicArn, description: 'ARN del Topic SNS para alertas al equipo interno' });
    new CfnOutput(this, 'SesEmailOrigen',    { value: sesEmailOrigen, description: 'Email autorizado como origen en SES' });
  }
}
