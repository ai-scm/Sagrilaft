import * as cdk from 'aws-cdk-lib';
import { Duration, RemovalPolicy, CfnOutput } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as targets from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

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
//     -c keycloakDomainName=auth.miempresa.com
//
// Los 3 dominios deben apuntar (CNAME) al DNS del ALB que aparece en los
// outputs del deploy. El certificado ACM se valida automáticamente via DNS.
// ─────────────────────────────────────────────────────────────────────────────
const DEFAULT_DOMINIO          = 'sagrilaft.tudominio.com';   // TODO: reemplazar
const DEFAULT_DOMINIO_PORTAL   = 'portal.tudominio.com';      // TODO: reemplazar
const DEFAULT_DOMINIO_KEYCLOAK = 'auth.tudominio.com';        // TODO: reemplazar
const EC2_INSTANCE   = ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL);
const RDS_INSTANCE   = ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO);
const UBUNTU_AMI_PARAMETER = '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id';

export class SagrilaftStack extends cdk.Stack {
  constructor(scope: Construct, constructId: string, props?: cdk.StackProps) {
    super(scope, constructId, props);

    const ambiente = String(this.node.tryGetContext('environment') ?? 'prod');
    const dominio = String(this.node.tryGetContext('domainName') ?? DEFAULT_DOMINIO);
    const dominioPortal = String(this.node.tryGetContext('portalDomainName') ?? DEFAULT_DOMINIO_PORTAL);
    const dominioKeycloak = String(this.node.tryGetContext('keycloakDomainName') ?? DEFAULT_DOMINIO_KEYCLOAK);
    const certArn = String(this.node.tryGetContext('certificateArn') ?? '');

    cdk.Tags.of(this).add('Project', 'sagrilaft');
    cdk.Tags.of(this).add('Environment', ambiente);

    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
    });

    const sgAlb = new ec2.SecurityGroup(this, 'SgAlb', {
      vpc,
      description: 'ALB',
    });
    sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'HTTP');
    sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS');

    const sgEc2 = new ec2.SecurityGroup(this, 'SgEc2', {
      vpc,
      description: 'EC2 app',
    });
    sgEc2.addIngressRule(sgAlb, ec2.Port.tcp(80), 'desde ALB -> frontend');
    sgEc2.addIngressRule(sgAlb, ec2.Port.tcp(81), 'desde ALB -> portal interno');
    sgEc2.addIngressRule(sgAlb, ec2.Port.tcp(8080), 'desde ALB -> Keycloak');

    const sgRds = new ec2.SecurityGroup(this, 'SgRds', {
      vpc,
      description: 'RDS postgres',
    });
    sgRds.addIngressRule(sgEc2, ec2.Port.tcp(5432), 'desde EC2');

    // ─────────────────────────────────────────────────────────────────────────
    // S3: estructura de carpetas por empresa.
    //
    // Cada empresa tiene su propia carpeta raíz (creada en el backend
    // al radicar el primer formulario):
    //
    //   s3://bucket/<nit-o-id-empresa>/adjuntos/   ← docs subidos al formulario
    //   s3://bucket/<nit-o-id-empresa>/formularios/ ← PDF del formulario radicado
    //   s3://bucket/<nit-o-id-empresa>/manuales/    ← cargas manuales del portal
    //   s3://bucket/<nit-o-id-empresa>/reportes/    ← reportes finales
    //   s3://bucket/tmp/                            ← archivos temporales (expiran 1 día)
    //
    // El backend genera presigned URLs para descargas desde el portal interno.
    // ─────────────────────────────────────────────────────────────────────────
    const bucket = new s3.Bucket(this, 'Uploads', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'expire-tmp',
          prefix: 'tmp/',
          expiration: Duration.days(1),
        },
      ],
    });

    const dbSecret = new secretsmanager.Secret(this, 'DbSecret', {
      secretName: `sagrilaft/${ambiente}/db_password`,
      generateSecretString: {
        secretStringTemplate: '{"username": "sagrilaft_user"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    // ZohoSign: servicio de firma electrónica.
    // El backend usa estas credenciales para:
    //   1. Enviar el PDF del formulario a ZohoSign al aprobar.
    //   2. Recibir el webhook de ZohoSign cuando el firmante completa la firma.
    //   3. Descargar el PDF firmado y almacenarlo en S3.
    // TODO: reemplazar los valores 'REPLACE_ME' con las credenciales reales de ZohoSign
    //       (obtenidas en https://sign.zoho.com → Settings → API).
    const zohoSecret = new secretsmanager.Secret(this, 'ZohoCredentialsSecret', {
      secretName: `sagrilaft/${ambiente}/zoho_credentials`,
      secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
        client_id:      'REPLACE_ME',  // ZohoSign OAuth client_id
        client_secret:  'REPLACE_ME',  // ZohoSign OAuth client_secret
        refresh_token:  'REPLACE_ME',  // ZohoSign OAuth refresh_token
        webhook_secret: 'REPLACE_ME',  // Secret para validar webhooks entrantes de ZohoSign
      })),
    });

    const keycloakAdminSecret = new secretsmanager.Secret(this, 'KeycloakAdminSecret', {
      secretName: `sagrilaft/${ambiente}/keycloak_admin_pass`,
      generateSecretString: {
        secretStringTemplate: '{"username": "admin"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    const smtpSecret = new secretsmanager.Secret(this, 'SmtpCredentialsSecret', {
      secretName: `sagrilaft/${ambiente}/smtp_credentials`,
      generateSecretString: {
        secretStringTemplate: '{"username": "REPLACE_ME"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    const db = new rds.DatabaseInstance(this, 'Postgres', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      instanceType: RDS_INSTANCE,
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
      securityGroups: [sgRds],
      databaseName: 'sagrilaft',
      credentials: rds.Credentials.fromSecret(dbSecret),
      multiAz: false,
      storageEncrypted: true,
      deletionProtection: true,
      backupRetention: Duration.days(7),
      removalPolicy: RemovalPolicy.RETAIN,
    });

    const roleEc2 = new iam.Role(this, 'Ec2Role', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });

    bucket.grantReadWrite(roleEc2);
    dbSecret.grantRead(roleEc2);
    zohoSecret.grantRead(roleEc2);   // ZohoSign: firma electrónica
    keycloakAdminSecret.grantRead(roleEc2);
    smtpSecret.grantRead(roleEc2);

    roleEc2.addToPolicy(new iam.PolicyStatement({
      sid: 'Bedrock',
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: ['*'],
    }));

    roleEc2.addToPolicy(new iam.PolicyStatement({
      sid: 'Ses',
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendRawEmail', 'ses:SendEmail'],
      resources: ['*'],
    }));

    const certificado = certArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', certArn)
      : new acm.Certificate(this, 'Cert', {
        domainName: dominio,
        subjectAlternativeNames: [dominioPortal, dominioKeycloak],
        validation: acm.CertificateValidation.fromDns(),
      });

    const userData = ec2.UserData.forLinux();
    userData.addCommands(
      'exec > >(tee /var/log/sagrilaft-user-data.log | logger -t sagrilaft-user-data -s 2>/dev/console) 2>&1',
      'set -euxo pipefail',
      'echo "Iniciando bootstrap base SAGRILAFT en Ubuntu"',
      'export DEBIAN_FRONTEND=noninteractive',
      'apt-get update -y',
      'apt-get install -y docker.io docker-compose-v2 awscli jq postgresql-client',
      'systemctl enable docker && systemctl start docker',
      'usermod -aG docker ubuntu',
      'mkdir -p /opt/sagrilaft /opt/sagrilaft/releases /opt/sagrilaft/shared /var/log/sagrilaft',
      'chown -R ubuntu:ubuntu /opt/sagrilaft /var/log/sagrilaft',
      'echo "Preparando base de datos keycloak si no existe"',
      'set +x',
      `DB_SECRET_JSON=$(aws secretsmanager get-secret-value --region ${cdk.Stack.of(this).region} --secret-id ${dbSecret.secretArn} --query SecretString --output text)`,
      'DB_USER=$(echo "$DB_SECRET_JSON" | jq -r .username)',
      'DB_PASSWORD=$(echo "$DB_SECRET_JSON" | jq -r .password)',
      `until PGPASSWORD="$DB_PASSWORD" psql -h ${db.dbInstanceEndpointAddress} -U "$DB_USER" -d sagrilaft -c "SELECT 1" >/dev/null 2>&1; do echo "Esperando RDS..."; sleep 10; done`,
      `if ! PGPASSWORD="$DB_PASSWORD" psql -h ${db.dbInstanceEndpointAddress} -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='keycloak'" | grep -q 1; then PGPASSWORD="$DB_PASSWORD" createdb -h ${db.dbInstanceEndpointAddress} -U "$DB_USER" keycloak; fi`,
      'unset DB_SECRET_JSON DB_PASSWORD',
      'set -x',
      'echo "EC2 lista para despliegue externo via CI/CD o scripts operativos"',
    );

    const ec2Instance = new ec2.Instance(this, 'Ec2', {
      instanceType: EC2_INSTANCE,
      machineImage: ec2.MachineImage.fromSsmParameter(UBUNTU_AMI_PARAMETER),
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
      securityGroup: sgEc2,
      role: roleEc2,
      userData,
      blockDevices: [
        {
          deviceName: '/dev/xvda',
          volume: ec2.BlockDeviceVolume.ebs(30, {
            encrypted: true,
          }),
        },
      ],
    });
    ec2Instance.node.addDependency(db);

    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc,
      internetFacing: true,
      securityGroup: sgAlb,
    });

    const targetApp = new elbv2.ApplicationTargetGroup(this, 'TgApp', {
      vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(ec2Instance.instanceId, 80)],
      healthCheck: {
        path: '/',
        healthyHttpCodes: '200-299',
      },
    });

    const targetKc = new elbv2.ApplicationTargetGroup(this, 'TgKeycloak', {
      vpc,
      port: 8080,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(ec2Instance.instanceId, 8080)],
      healthCheck: {
        path: '/realms/sagrilaft',
        healthyHttpCodes: '200-299',
      },
    });

    const targetPortal = new elbv2.ApplicationTargetGroup(this, 'TgPortal', {
      vpc,
      port: 81,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(ec2Instance.instanceId, 81)],
      healthCheck: {
        path: '/',
        healthyHttpCodes: '200-299',
      },
    });

    const listenerHttps = alb.addListener('Https', {
      port: 443,
      certificates: [certificado],
      defaultTargetGroups: [targetApp],
    });

    listenerHttps.addAction('PortalInterno', {
      priority: 10,
      conditions: [
        elbv2.ListenerCondition.hostHeaders([dominioPortal]),
      ],
      action: elbv2.ListenerAction.forward([targetPortal]),
    });

    listenerHttps.addAction('Keycloak', {
      priority: 20,
      conditions: [
        elbv2.ListenerCondition.hostHeaders([dominioKeycloak]),
      ],
      action: elbv2.ListenerAction.forward([targetKc]),
    });

    alb.addListener('Http', {
      port: 80,
      defaultAction: elbv2.ListenerAction.redirect({
        protocol: 'HTTPS',
        port: '443',
        permanent: true,
      }),
    });

    new CfnOutput(this, 'AlbDns', {
      value: alb.loadBalancerDnsName,
      description: 'Apunta tus dominios a este CNAME en Route 53 o tu DNS',
    });

    new CfnOutput(this, 'DominiosEsperados', {
      value: `${dominio}, ${dominioPortal}, ${dominioKeycloak}`,
      description: 'Hostnames que deben apuntar al ALB',
    });

    new CfnOutput(this, 'S3Bucket', {
      value: bucket.bucketName,
      description: 'Nombre del bucket S3 para uploads',
    });

    new CfnOutput(this, 'RdsEndpoint', {
      value: db.dbInstanceEndpointAddress,
      description: 'Host RDS PostgreSQL',
    });

    new CfnOutput(this, 'KeycloakDbName', {
      value: 'keycloak',
      description: 'Base de datos separada que usa Keycloak en la misma instancia RDS',
    });

    new CfnOutput(this, 'Ec2InstanceId', {
      value: ec2Instance.instanceId,
      description: 'ID de la instancia EC2 (para SSM Session Manager)',
    });

    new CfnOutput(this, 'Ec2BootstrapLogs', {
      value: 'sudo tail -n 200 /var/log/cloud-init-output.log && sudo tail -n 200 /var/log/sagrilaft-user-data.log',
      description: 'Comando para validar el arranque EC2 despues del deploy',
    });

    new CfnOutput(this, 'DbSecretArn', {
      value: dbSecret.secretArn,
      description: 'ARN del secreto con la contrasena de la BD',
    });
  }
}
