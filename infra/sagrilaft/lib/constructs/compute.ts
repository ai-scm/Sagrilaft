import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface ComputeProps {
  readonly vpc: ec2.Vpc;
  readonly securityGroup: ec2.SecurityGroup;
  readonly bucket: s3.Bucket;
  readonly db: rds.DatabaseInstance;
  readonly dbSecret: secretsmanager.Secret;
  readonly alertasTopic: sns.Topic;
  readonly sesEmailOrigen: string;
  /** Todos los ARNs de log groups (grupo + streams) para políticas IAM. */
  readonly logGroupArns: string[];
  /** Log group del bootstrap para la configuración del CloudWatch Agent. */
  readonly lgBootstrap: logs.LogGroup;
  /** Log groups individuales para inyectar en .env.aws. */
  readonly lgBackend: logs.LogGroup;
  readonly lgFrontend: logs.LogGroup;
  readonly lgPortal: logs.LogGroup;
  readonly lgKeycloak: logs.LogGroup;
  /** Callback para otorgar permisos de lectura de secretos al rol EC2. */
  readonly grantSecretsRead: (grantee: iam.IGrantable) => void;
}

const UBUNTU_AMI_PARAMETER = '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id';

/**
 * Compute: Rol IAM + EC2 + UserData.
 *
 * El UserData ejecuta al primer arranque:
 *   1. Instala Docker, Docker Compose, AWS CLI, PostgreSQL client
 *   2. Crea la base de datos keycloak en RDS si no existe
 *   3. Inyecta variables CDK en /opt/sagrilaft/.env.aws
 *   4. Instala y configura el CloudWatch Agent para logs de sistema
 */
export class Compute extends Construct {
  public readonly role: iam.Role;
  public readonly instance: ec2.Instance;

  constructor(scope: Construct, id: string, props: ComputeProps) {
    super(scope, id);

    this.role = this.buildRole(props);
    const userData = this.buildUserData(props);

    this.instance = new ec2.Instance(this, 'Ec2', {
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL),
      machineImage: ec2.MachineImage.fromSsmParameter(UBUNTU_AMI_PARAMETER),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: props.securityGroup,
      role: this.role,
      userData,
      blockDevices: [
        {
          deviceName: '/dev/xvda',
          volume: ec2.BlockDeviceVolume.ebs(30, { encrypted: true }),
        },
      ],
    });
    this.instance.node.addDependency(props.db);
  }

  // ── Rol IAM con principio de mínimo privilegio ─────────────────────────

  private buildRole(props: ComputeProps): iam.Role {
    const role = new iam.Role(this, 'Ec2Role', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });

    // Storage
    props.bucket.grantReadWrite(role);

    // Secrets (DB, Zoho, Keycloak, SMTP)
    props.grantSecretsRead(role);

    // Bedrock (Motor IA)
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'Bedrock',
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: ['*'],
    }));

    // SES (Correos transaccionales)
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'Ses',
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendRawEmail', 'ses:SendEmail'],
      resources: ['*'],
    }));

    // SNS (Alertas internas)
    props.alertasTopic.grantPublish(role);
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'SnsHealthCheck',
      effect: iam.Effect.ALLOW,
      actions: ['sns:GetTopicAttributes'],
      resources: [props.alertasTopic.topicArn],
    }));

    // CloudWatch Metrics (Observabilidad del backend)
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudWatchMetrics',
      effect: iam.Effect.ALLOW,
      actions: ['cloudwatch:PutMetricData'],
      resources: ['*'],
      conditions: {
        'StringEquals': { 'cloudwatch:namespace': 'SAGRILAFT' },
      },
    }));

    // CloudWatch Logs (Driver awslogs de Docker + CW Agent)
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:CreateLogStream',
        'logs:PutLogEvents',
        'logs:DescribeLogStreams',
        'logs:DescribeLogGroups',
      ],
      resources: props.logGroupArns,
    }));

    return role;
  }

  // ── UserData: bootstrap del EC2 ────────────────────────────────────────

  private buildUserData(props: ComputeProps): ec2.UserData {
    const region = cdk.Stack.of(this).region;
    const userData = ec2.UserData.forLinux();

    userData.addCommands(
      // Logging del bootstrap
      'exec > >(tee /var/log/sagrilaft-user-data.log | logger -t sagrilaft-user-data -s 2>/dev/console) 2>&1',
      'set -euxo pipefail',
      'echo "Iniciando bootstrap base SAGRILAFT en Ubuntu"',

      // Instalar dependencias del sistema
      'export DEBIAN_FRONTEND=noninteractive',
      'apt-get update -y',
      'apt-get install -y docker.io docker-compose-v2 awscli jq postgresql-client',
      'systemctl enable docker && systemctl start docker',
      'usermod -aG docker ubuntu',

      // Preparar directorios
      'mkdir -p /opt/sagrilaft /opt/sagrilaft/releases /opt/sagrilaft/shared /var/log/sagrilaft',
      'chown -R ubuntu:ubuntu /opt/sagrilaft /var/log/sagrilaft',

      // Crear base de datos keycloak en RDS si no existe
      'echo "Preparando base de datos keycloak si no existe"',
      'set +x',
      `DB_SECRET_JSON=$(aws secretsmanager get-secret-value --region ${region} --secret-id ${props.dbSecret.secretArn} --query SecretString --output text)`,
      'DB_USER=$(echo "$DB_SECRET_JSON" | jq -r .username)',
      'DB_PASSWORD=$(echo "$DB_SECRET_JSON" | jq -r .password)',
      `until PGPASSWORD="$DB_PASSWORD" psql -h ${props.db.dbInstanceEndpointAddress} -U "$DB_USER" -d sagrilaft -c "SELECT 1" >/dev/null 2>&1; do echo "Esperando RDS..."; sleep 10; done`,
      `if ! PGPASSWORD="$DB_PASSWORD" psql -h ${props.db.dbInstanceEndpointAddress} -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='keycloak'" | grep -q 1; then PGPASSWORD="$DB_PASSWORD" createdb -h ${props.db.dbInstanceEndpointAddress} -U "$DB_USER" keycloak; fi`,
      'unset DB_SECRET_JSON DB_PASSWORD',
      'set -x',

      // Inyectar variables CDK → .env.aws (leído por docker-compose.prod.yml)
      'echo "Inyectando variables de infraestructura CDK para el backend"',
      `echo "SNS_TOPIC_ARN=${props.alertasTopic.topicArn}" > /opt/sagrilaft/.env.aws`,
      `echo "SES_EMAIL_ORIGEN=${props.sesEmailOrigen}" >> /opt/sagrilaft/.env.aws`,
      `echo "CW_LOG_GROUP_BACKEND=${props.lgBackend.logGroupName}" >> /opt/sagrilaft/.env.aws`,
      `echo "CW_LOG_GROUP_FRONTEND=${props.lgFrontend.logGroupName}" >> /opt/sagrilaft/.env.aws`,
      `echo "CW_LOG_GROUP_PORTAL=${props.lgPortal.logGroupName}" >> /opt/sagrilaft/.env.aws`,
      `echo "CW_LOG_GROUP_KEYCLOAK=${props.lgKeycloak.logGroupName}" >> /opt/sagrilaft/.env.aws`,
      'chown ubuntu:ubuntu /opt/sagrilaft/.env.aws',

      // Instalar y configurar CloudWatch Agent (logs de bootstrap y sistema)
      'echo "Instalando CloudWatch Agent para logs de sistema"',
      'curl -sO https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb',
      'dpkg -i amazon-cloudwatch-agent.deb && rm amazon-cloudwatch-agent.deb',
      ...this.buildCwAgentConfig(props.lgBootstrap),

      'echo "EC2 lista para despliegue externo via CI/CD o scripts operativos"',
    );

    return userData;
  }

  // ── Configuración del CloudWatch Agent ─────────────────────────────────

  private buildCwAgentConfig(lgBootstrap: logs.LogGroup): string[] {
    const configPath = '/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json';
    const ctlPath = '/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl';
    const logGroupName = lgBootstrap.logGroupName;

    const config = JSON.stringify({
      logs: {
        logs_collected: {
          files: {
            collect_list: [
              {
                file_path: '/var/log/sagrilaft-user-data.log',
                log_group_name: logGroupName,
                log_stream_name: 'userdata',
                timestamp_format: '%Y-%m-%dT%H:%M:%S',
              },
              {
                file_path: '/var/log/cloud-init-output.log',
                log_group_name: logGroupName,
                log_stream_name: 'cloud-init',
                timestamp_format: '%Y-%m-%dT%H:%M:%S',
              },
              {
                file_path: '/var/log/syslog',
                log_group_name: logGroupName,
                log_stream_name: 'syslog',
                timestamp_format: '%b %d %H:%M:%S',
              },
            ],
          },
        },
      },
    }, null, 2);

    return [
      `cat > ${configPath} << 'CWEOF'\n${config}\nCWEOF`,
      `${ctlPath} -a fetch-config -m ec2 -c file:${configPath} -s`,
      'echo "CloudWatch Agent configurado y activo"',
    ];
  }
}
