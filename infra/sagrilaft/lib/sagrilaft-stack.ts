import * as cdk from 'aws-cdk-lib';
import { CfnOutput } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import { Construct } from 'constructs';

import { Networking } from './constructs/networking';
import { Storage } from './constructs/storage';
import { Secrets } from './constructs/secrets';
import { Notifications } from './constructs/notifications';
import { Database } from './constructs/database';
import { LoadBalancer } from './constructs/load-balancer';
import { Ecr } from './constructs/ecr';
import { ConfigParameters } from './constructs/config-parameters';
import { EcsFargate } from './constructs/ecs-fargate';
import { CortafuegosWeb } from './constructs/cortafuegos-web';
import { ObservabilidadAlarmas } from './constructs/observabilidad-alarmas';
import { DashboardTecnico } from './constructs/dashboard-tecnico';
import { DashboardNegocio } from './constructs/dashboard-negocio';
import { DEFAULT_BEDROCK_MODEL_ID, SAGRILAFT_DB_NAME } from './deployment-constants';

// ─────────────────────────────────────────────────────────────────────────────
// Dominios productivos actuales.
//
//   Formulario público : DEFAULT_DOMINIO          (ej: forms-sagrilaft.ia.blend360.com)
//   Portal interno     : DEFAULT_DOMINIO_PORTAL    (ej: sagrilaft.ia.blend360.com)
//   Autenticación      : DEFAULT_DOMINIO_KEYCLOAK  (ej: login-sagrilaft.ia.blend360.com)
//
// Para desplegar con los dominios reales:
//   npx cdk deploy \
//     -c hostedZoneName=ia.blend360.com \
//     -c hostedZoneId=Z10446292T6I6L9P7R8AQ \
//     -c domainName=forms-sagrilaft.ia.blend360.com \
//     -c portalDomainName=sagrilaft.ia.blend360.com \
//     -c keycloakDomainName=login-sagrilaft.ia.blend360.com \
//     -c sesEmailOrigen=legal@blend360.com.com \
//     -c snsAlertasSub=equipo-interno@ia.blend360.com \
//     -c imageTag=<commit-sha> \
//     -c bedrockModelId=<model-id-o-inference-profile>
// ─────────────────────────────────────────────────────────────────────────────
const DEFAULT_HOSTED_ZONE = 'ia.blend360.com';
const DEFAULT_HOSTED_ZONE_ID = 'Z10446292T6I6L9P7R8AQ';
const DEFAULT_DOMINIO = 'forms-sagrilaft.ia.blend360.com';
const DEFAULT_DOMINIO_PORTAL = 'sagrilaft.ia.blend360.com';
const DEFAULT_DOMINIO_KEYCLOAK = 'login-sagrilaft.ia.blend360.com';

export class SagrilaftStack extends cdk.Stack {
  constructor(scope: Construct, constructId: string, props?: cdk.StackProps) {
    super(scope, constructId, props);

    // ── Parámetros de contexto ─────────────────────────────────────────────
    const ambiente = String(this.node.tryGetContext('environment') ?? 'prod');
    const hostedZoneName = String(this.node.tryGetContext('hostedZoneName') ?? DEFAULT_HOSTED_ZONE);
    const hostedZoneId = String(this.node.tryGetContext('hostedZoneId') ?? DEFAULT_HOSTED_ZONE_ID);
    const dominio = String(this.node.tryGetContext('domainName') ?? DEFAULT_DOMINIO);
    const dominioPortal = String(this.node.tryGetContext('portalDomainName') ?? DEFAULT_DOMINIO_PORTAL);
    const dominioKeycloak = String(this.node.tryGetContext('keycloakDomainName') ?? DEFAULT_DOMINIO_KEYCLOAK);
    const certArn = String(this.node.tryGetContext('certificateArn') ?? '');
    const defaultSesEmailOrigen = ambiente === 'staging'
      ? 'legal@blend360.com'
      : 'legal@blend360.com';
    const defaultAlertasEmailDestino = [
      'Bryan.Ariza@blend360.com',
    ].join(',');
    const sesEmailOrigen = String(this.node.tryGetContext('sesEmailOrigen') ?? defaultSesEmailOrigen);
    const snsAlertasSub = String(this.node.tryGetContext('snsAlertasSub') ?? defaultAlertasEmailDestino);
    const imageTag = String(this.node.tryGetContext('imageTag') ?? '');
    const bedrockModelId = String(this.node.tryGetContext('bedrockModelId') ?? DEFAULT_BEDROCK_MODEL_ID);
    const sagrilaftApiUrl = String(this.node.tryGetContext('sagrilaftApiUrl') ?? '');
    const desiredCountRaw = String(this.node.tryGetContext('desiredCount') ?? '2');
    const desiredCount = Number.parseInt(desiredCountRaw, 10);

    if (['staging', 'prod'].includes(ambiente) && !imageTag) {
      throw new Error(`El ambiente ${ambiente} requiere -c imageTag=<commit-sha>. No usar latest en despliegues controlados.`);
    }
    if (['staging', 'prod'].includes(ambiente) && !bedrockModelId) {
      throw new Error(`El ambiente ${ambiente} requiere -c bedrockModelId=<model-id-o-inference-profile>. No usar credenciales AWS personales.`);
    }
    if (['staging', 'prod'].includes(ambiente) && !sagrilaftApiUrl) {
      throw new Error(
        `El ambiente ${ambiente} requiere -c sagrilaftApiUrl=<url-api-tusdatos>. ` +
        'La verificacion de listas de cautela no puede quedar sin URL real en produccion/staging.',
      );
    }
    if (!Number.isInteger(desiredCount) || desiredCount < 0) {
      throw new Error(`desiredCount invalido: ${desiredCountRaw}. Use 0 para bootstrap o 1+ para activar servicios.`);
    }
    cdk.Tags.of(this).add('Project', 'sagrilaft');
    cdk.Tags.of(this).add('Environment', ambiente);

    const hostedZone = hostedZoneName && hostedZoneId
      ? route53.HostedZone.fromHostedZoneAttributes(this, 'HostedZone', {
        hostedZoneId,
        zoneName: hostedZoneName,
      })
      : undefined;

    // ── Constructs ─────────────────────────────────────────────────────────
    const networking = new Networking(this, 'Networking');
    const storage = new Storage(this, 'Storage', { 
      ambiente,
      dominioPortal,
    });
    const secrets = new Secrets(this, 'Secrets', { ambiente });
    const notifications = new Notifications(this, 'Notifications', { ambiente, sesEmailOrigen, snsAlertasSub });
    const ecrRepos = new Ecr(this, 'Ecr', { ambiente });
    const configParams = new ConfigParameters(this, 'ConfigParameters', {
      ambiente,
      dominio,
      dominioPortal,
      dominioKeycloak,
      s3BucketName: storage.bucket.bucketName,
      sesEmailOrigen,
      alertasEmailDestino: snsAlertasSub,
      bedrockModelId,
      sagrilaftApiUrl,
    });

    const database = new Database(this, 'Database', {
      vpc: networking.vpc,
      securityGroup: networking.sgRds,
      credentialsSecret: secrets.dbSecret,
      ambiente,
    });

    const ecsFargate = new EcsFargate(this, 'EcsFargate', {
      ambiente,
      imageTag: imageTag || 'dev',
      desiredCount,
      vpc: networking.vpc,
      securityGroup: networking.sgEcs,
      bucket: storage.bucket,
      db: database.instance,
      alertasTopic: notifications.alertasTopic,
      backendRepo: ecrRepos.backendRepo,
      formularioPublicoRepo: ecrRepos.formularioPublicoRepo,
      portalInternoRepo: ecrRepos.portalInternoRepo,
      keycloakRepo: ecrRepos.keycloakRepo,
      dbSecret: secrets.dbSecret,
      appSecret: secrets.appSecret,
      zohoSecret: secrets.zohoSecret,
      keycloakAdminSecret: secrets.keycloakAdminSecret,
      smtpSecret: secrets.smtpSecret,
      sagrilaftSecret: secrets.sagrilaftSecret,
      configParameterNames: configParams.parameterNames,
      configParameterNameByKey: configParams.parameterNameByKey,
      configParameterByKey: configParams.parameterByKey,
      grantSecretsRead: (grantee) => secrets.grantReadAll(grantee),
      grantEcrPull: (grantee) => ecrRepos.grantPull(grantee),
    });

    const certificado = certArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', certArn)
      : new acm.Certificate(this, 'Cert', {
        domainName: dominio,
        subjectAlternativeNames: [dominioPortal, dominioKeycloak],
        validation: hostedZone
          ? acm.CertificateValidation.fromDns(hostedZone)
          : acm.CertificateValidation.fromDns(),
      });

    const lb = new LoadBalancer(this, 'Lb', {
      vpc: networking.vpc,
      securityGroup: networking.sgAlb,
      targetFormularioPublico: ecsFargate.frontend.targetGroup,
      targetPortalInterno: ecsFargate.portal.targetGroup,
      targetBackend: ecsFargate.backend.targetGroup,
      targetKeycloak: ecsFargate.keycloak.targetGroup,
      certificado,
      dominio,
      dominioPortal,
      dominioKeycloak,
    });

    const cortafuegos = new CortafuegosWeb(this, 'CortafuegosWeb', {
      arnBalanceadorCarga: lb.alb.loadBalancerArn,
    });

    const alarmas = new ObservabilidadAlarmas(this, 'AlarmasCriticas', {
      balanceadorCarga: lb.alb,
      servicioBackend: ecsFargate.backend.service,
      topicAlertas: notifications.alertasTopic,
      ambiente,
    });

    const dashboardTecnico = new DashboardTecnico(this, 'DashboardTecnico', {
      balanceadorCarga: lb.alb,
      servicioBackend: ecsFargate.backend.service,
      servicioPortal: ecsFargate.portal.service,
      dbInstance: database.instance,
      ambiente,
    });

    const dashboardNegocio = new DashboardNegocio(this, 'DashboardNegocio', {
      ambiente,
    });

    if (hostedZone) {
      const albTarget = route53.RecordTarget.fromAlias(new targets.LoadBalancerTarget(lb.alb));

      new route53.ARecord(this, 'FormularioPublicoDnsRecord', {
        zone: hostedZone,
        recordName: dominio,
        target: albTarget,
      });

      new route53.ARecord(this, 'PortalInternoDnsRecord', {
        zone: hostedZone,
        recordName: dominioPortal,
        target: albTarget,
      });

      new route53.ARecord(this, 'KeycloakDnsRecord', {
        zone: hostedZone,
        recordName: dominioKeycloak,
        target: albTarget,
      });
    }

    // ── Outputs ────────────────────────────────────────────────────────────
    new CfnOutput(this, 'AlbDns', { value: lb.alb.loadBalancerDnsName, description: 'DNS del ALB publico creado para SAGRILAFT' });
    new CfnOutput(this, 'HostedZoneName', { value: hostedZoneName || 'no-configurada', description: 'Zona Route 53 usada para crear registros A Alias' });
    new CfnOutput(this, 'DominiosEsperados', { value: `${dominio}, ${dominioPortal}, ${dominioKeycloak}`, description: 'Hostnames que deben apuntar al ALB' });
    new CfnOutput(this, 'S3Bucket', { value: storage.bucket.bucketName, description: 'Nombre del bucket S3 para uploads' });
    new CfnOutput(this, 'RdsEndpoint', { value: database.instance.dbInstanceEndpointAddress, description: 'Host RDS PostgreSQL' });
    new CfnOutput(this, 'KeycloakDbName', { value: SAGRILAFT_DB_NAME, description: 'Base de datos RDS usada por Keycloak en ECS' });
    new CfnOutput(this, 'DbSecretArn', { value: secrets.dbSecret.secretArn, description: 'ARN del secreto con la contrasena de la BD' });
    new CfnOutput(this, 'AppSecretArn', { value: secrets.appSecret.secretArn, description: 'ARN del secreto SECRET_KEY de la aplicacion' });
    new CfnOutput(this, 'ZohoSecretArn', { value: secrets.zohoSecret.secretArn, description: 'ARN del secreto de credenciales Zoho' });
    new CfnOutput(this, 'SmtpSecretArn', { value: secrets.smtpSecret.secretArn, description: 'ARN del secreto de credenciales SMTP/SES' });
    new CfnOutput(this, 'SagrilaftSecretArn', { value: secrets.sagrilaftSecret.secretArn, description: 'ARN del secreto de credenciales de la API de listas de cautela (tusdatos.co)' });
    new CfnOutput(this, 'KeycloakAdminSecretArn', { value: secrets.keycloakAdminSecret.secretArn, description: 'ARN del secreto admin de Keycloak' });
    new CfnOutput(this, 'RuntimeConfigPrefix', { value: `/sagrilaft/${ambiente}/config/`, description: 'Prefijo SSM Parameter Store para runtime config no sensible' });
    new CfnOutput(this, 'BedrockModelId', { value: bedrockModelId, description: 'Modelo o inference profile Bedrock inyectado al backend desde SSM' });
    new CfnOutput(this, 'SnsAlertasTopicArn', { value: notifications.alertasTopic.topicArn, description: 'ARN del Topic SNS para alertas al equipo interno' });
    new CfnOutput(this, 'SesEmailOrigen', { value: sesEmailOrigen, description: 'Email autorizado como origen en SES' });
    new CfnOutput(this, 'EcrBackendUri', { value: ecrRepos.backendRepo.repositoryUri, description: 'URI del repositorio ECR Backend' });
    new CfnOutput(this, 'EcrFormularioPublicoUri', { value: ecrRepos.formularioPublicoRepo.repositoryUri, description: 'URI del repositorio ECR Formulario Publico' });
    new CfnOutput(this, 'EcrPortalInternoUri', { value: ecrRepos.portalInternoRepo.repositoryUri, description: 'URI del repositorio ECR Portal Interno' });
    new CfnOutput(this, 'EcrKeycloakUri', { value: ecrRepos.keycloakRepo.repositoryUri, description: 'URI del repositorio ECR Keycloak' });
    new CfnOutput(this, 'EcsClusterName', { value: ecsFargate.cluster.clusterName, description: 'Cluster ECS/Fargate productivo' });
    new CfnOutput(this, 'EcsDesiredCount', { value: String(desiredCount), description: 'Desired count configurado para servicios ECS' });
    new CfnOutput(this, 'EcsSecurityGroupId', { value: networking.sgEcs.securityGroupId, description: 'Security Group para servicios ECS Fargate' });
    new CfnOutput(this, 'EcsTaskExecutionRoleArn', { value: ecsFargate.executionRole.roleArn, description: 'Task Execution Role ECS para pull ECR, logs y secrets/SSM' });
    new CfnOutput(this, 'EcsBackendTaskRoleArn', { value: ecsFargate.backendTaskRole.roleArn, description: 'Task Role ECS para backend' });
    new CfnOutput(this, 'EcsFrontendServiceName', { value: ecsFargate.frontend.service.serviceName, description: 'Servicio ECS formulario publico conectado al ALB' });
    new CfnOutput(this, 'EcsPortalServiceName', { value: ecsFargate.portal.service.serviceName, description: 'Servicio ECS portal interno conectado al ALB' });
    new CfnOutput(this, 'EcsBackendServiceName', { value: ecsFargate.backend.service.serviceName, description: 'Servicio ECS backend' });
    new CfnOutput(this, 'EcsKeycloakServiceName', { value: ecsFargate.keycloak.service.serviceName, description: 'Servicio ECS Keycloak conectado al ALB' });
    new CfnOutput(this, 'EcsBackendTargetGroupArn', { value: ecsFargate.backend.targetGroup.targetGroupArn, description: 'Target Group ECS backend' });
    new CfnOutput(this, 'EcsMigrationTaskDefinitionArn', { value: ecsFargate.migrationTaskDefinition.taskDefinitionArn, description: 'Task Definition ECS para ejecutar migraciones Alembic puntuales' });
    new CfnOutput(this, 'EcsMigrationLogGroupName', { value: ecsFargate.migrationLogGroup.logGroupName, description: 'Log Group CloudWatch de migraciones Alembic' });
  }
}
