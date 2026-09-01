import { Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { SAGRILAFT_DB_NAME } from '../deployment-constants';

export interface EcsFargateProps {
  readonly ambiente: string;
  readonly imageTag: string;
  readonly desiredCount: number;
  readonly backendMaxCapacity: number;
  readonly vpc: ec2.Vpc;
  readonly serviceSubnetType: ec2.SubnetType;
  readonly securityGroup: ec2.SecurityGroup;
  readonly bucket: s3.Bucket;
  readonly db: rds.DatabaseInstance;
  readonly alertasTopic: sns.Topic;
  readonly backendRepo: ecr.Repository;
  readonly formularioPublicoRepo: ecr.Repository;
  readonly portalInternoRepo: ecr.Repository;
  readonly keycloakRepo: ecr.Repository;
  readonly dbSecret: secretsmanager.Secret;
  readonly appSecret: secretsmanager.Secret;
  readonly zohoSecret: secretsmanager.Secret;
  readonly keycloakAdminSecret: secretsmanager.Secret;
  readonly smtpSecret: secretsmanager.Secret;
  readonly sagrilaftSecret: secretsmanager.Secret;
  readonly configParameterNames: string[];
  readonly configParameterNameByKey: Record<string, string>;
  readonly configParameterByKey: Record<string, ssm.IStringParameter>;
  readonly grantSecretsRead: (grantee: iam.IGrantable) => void;
  readonly grantEcrPull: (grantee: iam.IGrantable) => void;
}

interface AppService {
  readonly taskDefinition: ecs.FargateTaskDefinition;
  readonly service: ecs.FargateService;
  readonly targetGroup: elbv2.ApplicationTargetGroup;
  readonly logGroup: logs.LogGroup;
}

/**
 * ECS/Fargate productivo: cluster, task definitions, services y target groups.
 * Usa VPC, subnets y Security Groups de la red compartida.
 *
 * El ALB enruta directamente a estos services.
 */
export class EcsFargate extends Construct {
  public readonly cluster: ecs.Cluster;
  public readonly executionRole: iam.Role;
  public readonly frontendTaskRole: iam.Role;
  public readonly portalTaskRole: iam.Role;
  public readonly backendTaskRole: iam.Role;
  public readonly keycloakTaskRole: iam.Role;
  public readonly migrationTaskDefinition: ecs.FargateTaskDefinition;
  public readonly migrationLogGroup: logs.LogGroup;
  public readonly frontend: AppService;
  public readonly portal: AppService;
  public readonly backend: AppService;
  public readonly keycloak: AppService;

  constructor(scope: Construct, id: string, props: EcsFargateProps) {
    super(scope, id);

    this.cluster = new ecs.Cluster(this, 'Cluster', {
      vpc: props.vpc,
      clusterName: `sagrilaft-${props.ambiente}`,
      containerInsightsV2: ecs.ContainerInsights.ENABLED,
      defaultCloudMapNamespace: {
        name: `sagrilaft-${props.ambiente}.local`,
      },
    });

    this.executionRole = this.buildExecutionRole(props);
    this.frontendTaskRole = this.buildFrontendRole('FrontendTaskRole', props);
    this.portalTaskRole = this.buildFrontendRole('PortalTaskRole', props);
    this.backendTaskRole = this.buildBackendRole(props);
    this.keycloakTaskRole = this.buildKeycloakRole(props);

    const migration = this.buildMigrationTaskDefinition(props);
    this.migrationTaskDefinition = migration.taskDefinition;
    this.migrationLogGroup = migration.logGroup;

    this.backend = this.buildBackendService(props);
    this.keycloak = this.buildKeycloakService(props);
    this.frontend = this.buildFrontendService(props);
    this.portal = this.buildPortalService(props);
  }

  private buildBackendService(props: EcsFargateProps): AppService {
    const logGroup = this.buildLogGroup('BackendLogGroup', props.ambiente, 'backend', logs.RetentionDays.ONE_MONTH);
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'BackendTaskDefinition', {
      cpu: 512,
      memoryLimitMiB: 1024,
      executionRole: this.executionRole,
      taskRole: this.backendTaskRole,
      family: `sagrilaft-${props.ambiente}-backend`,
    });

    const container = taskDefinition.addContainer('backend', {
      image: ecs.ContainerImage.fromEcrRepository(props.backendRepo, props.imageTag),
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: 'backend' }),
      environment: this.backendEnvironment(props, logGroup, { RUN_MODE: 'server' }),
      secrets: this.backendSecrets(props, 'Backend'),
      command: [
        'sh',
        '-c',
        [
          'export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DATABASE_HOST}:5432/${DATABASE_NAME}"',
          'exec sh entrypoint.sh',
        ].join('; '),
      ],
      healthCheck: {
        command: ['CMD-SHELL', 'python -c "import urllib.request; urllib.request.urlopen(\'http://localhost:8000/health\')"'],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(10),
        retries: 3,
        startPeriod: Duration.seconds(120),
      },
    });
    container.addPortMappings({ containerPort: 8000 });

    const targetGroup = this.buildTargetGroup('BackendTargetGroup', props, 'backend', 8000, '/health');
    const service = this.buildService('BackendService', props, taskDefinition, props.desiredCount, 'backend');
    service.attachToApplicationTargetGroup(targetGroup);
    service.node.addDependency(props.db);
    this.configureBackendAutoScaling(service, props);

    return { taskDefinition, service, targetGroup, logGroup };
  }

  /**
   * Auto Scaling solo para el backend: es el único servicio con carga variable real
   * (extracción con Bedrock, generación de PDF). Frontend/Portal son estáticos y
   * Keycloak no escala aquí por la complejidad de clustering entre nodos dinámicos.
   *
   * Se omite durante el bootstrap (desiredCount=0) para no interferir con el primer
   * despliegue sin tráfico, y si backendMaxCapacity no deja rango por encima de
   * desiredCount (autoscaling deshabilitado a propósito, ej. entornos de prueba).
   */
  private configureBackendAutoScaling(service: ecs.FargateService, props: EcsFargateProps): void {
    if (props.desiredCount === 0 || props.backendMaxCapacity <= props.desiredCount) {
      return;
    }

    const scaling = service.autoScaleTaskCount({
      minCapacity: props.desiredCount,
      maxCapacity: props.backendMaxCapacity,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 60,
      scaleInCooldown: Duration.seconds(300),
      scaleOutCooldown: Duration.seconds(60),
    });

    scaling.scaleOnMemoryUtilization('MemoryScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: Duration.seconds(300),
      scaleOutCooldown: Duration.seconds(60),
    });
  }

  private buildMigrationTaskDefinition(props: EcsFargateProps): { taskDefinition: ecs.FargateTaskDefinition; logGroup: logs.LogGroup } {
    const logGroup = this.buildLogGroup('MigrationLogGroup', props.ambiente, 'migration', logs.RetentionDays.ONE_MONTH);
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'MigrationTaskDefinition', {
      cpu: 512,
      memoryLimitMiB: 1024,
      executionRole: this.executionRole,
      taskRole: this.backendTaskRole,
      family: `sagrilaft-${props.ambiente}-migration`,
    });

    taskDefinition.addContainer('migration', {
      image: ecs.ContainerImage.fromEcrRepository(props.backendRepo, props.imageTag),
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: 'migration' }),
      environment: this.backendEnvironment(props, logGroup, { RUN_MODE: 'migrate' }),
      secrets: this.backendSecrets(props, 'Migration'),
      command: [
        'sh',
        '-c',
        [
          'export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DATABASE_HOST}:5432/${DATABASE_NAME}"',
          'exec sh entrypoint.sh',
        ].join('; '),
      ],
    });

    taskDefinition.node.addDependency(props.db);
    return { taskDefinition, logGroup };
  }

  private buildKeycloakService(props: EcsFargateProps): AppService {
    const logGroup = this.buildLogGroup('KeycloakLogGroup', props.ambiente, 'keycloak', logs.RetentionDays.TWO_WEEKS);
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'KeycloakTaskDefinition', {
      cpu: 512,
      memoryLimitMiB: 1024,
      executionRole: this.executionRole,
      taskRole: this.keycloakTaskRole,
      family: `sagrilaft-${props.ambiente}-keycloak`,
    });

    const container = taskDefinition.addContainer('keycloak', {
      image: ecs.ContainerImage.fromEcrRepository(props.keycloakRepo, props.imageTag),
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: 'keycloak' }),
      command: ['start', '--import-realm'],
      environment: {
        KC_DB: 'postgres',
        KC_DB_URL: `jdbc:postgresql://${props.db.dbInstanceEndpointAddress}:5432/${SAGRILAFT_DB_NAME}`,
        KC_PROXY_HEADERS: 'xforwarded',
        KC_HTTP_ENABLED: 'true',
        KC_HOSTNAME_STRICT: 'false',
      },
      secrets: {
        KEYCLOAK_ADMIN: ecs.Secret.fromSecretsManager(props.keycloakAdminSecret, 'username'),
        KEYCLOAK_ADMIN_PASSWORD: ecs.Secret.fromSecretsManager(props.keycloakAdminSecret, 'password'),
        KC_HOSTNAME: this.ssmSecret('KEYCLOAK_HOSTNAME', props),
        KC_DB_USERNAME: ecs.Secret.fromSecretsManager(props.dbSecret, 'username'),
        KC_DB_PASSWORD: ecs.Secret.fromSecretsManager(props.dbSecret, 'password'),
      },
      healthCheck: {
        command: ['CMD-SHELL', 'bash -ec "</dev/tcp/127.0.0.1/8080"'],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(10),
        retries: 10,
        startPeriod: Duration.seconds(180),
      },
    });
    container.addPortMappings({ containerPort: 8080 });

    const targetGroup = this.buildTargetGroup('KeycloakTargetGroup', props, 'keycloak', 8080, '/');
    const service = this.buildService('KeycloakService', props, taskDefinition, props.desiredCount, 'keycloak', {
      healthCheckGracePeriod: Duration.seconds(300),
    });
    service.attachToApplicationTargetGroup(targetGroup);
    service.node.addDependency(props.db);

    return { taskDefinition, service, targetGroup, logGroup };
  }

  private buildFrontendService(props: EcsFargateProps): AppService {
    return this.buildStaticFrontendService({
      idPrefix: 'Frontend',
      serviceName: 'frontend',
      repo: props.formularioPublicoRepo,
      taskRole: this.frontendTaskRole,
      props,
    });
  }

  private buildPortalService(props: EcsFargateProps): AppService {
    return this.buildStaticFrontendService({
      idPrefix: 'Portal',
      serviceName: 'portal',
      repo: props.portalInternoRepo,
      taskRole: this.portalTaskRole,
      props,
    });
  }

  private buildStaticFrontendService(input: {
    readonly idPrefix: string;
    readonly serviceName: string;
    readonly repo: ecr.Repository;
    readonly taskRole: iam.Role;
    readonly props: EcsFargateProps;
  }): AppService {
    const { idPrefix, serviceName, repo, taskRole, props } = input;
    const logGroup = this.buildLogGroup(`${idPrefix}LogGroup`, props.ambiente, serviceName, logs.RetentionDays.TWO_WEEKS);
    const taskDefinition = new ecs.FargateTaskDefinition(this, `${idPrefix}TaskDefinition`, {
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole: this.executionRole,
      taskRole,
      family: `sagrilaft-${props.ambiente}-${serviceName}`,
    });

    const container = taskDefinition.addContainer(serviceName, {
      image: ecs.ContainerImage.fromEcrRepository(repo, props.imageTag),
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: serviceName }),
      healthCheck: {
        command: ['CMD-SHELL', 'wget -qO- http://localhost:8080/ >/dev/null || exit 1'],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(10),
        retries: 3,
        startPeriod: Duration.seconds(30),
      },
    });
    container.addPortMappings({ containerPort: 8080 });

    const targetGroup = this.buildTargetGroup(`${idPrefix}TargetGroup`, props, serviceName, 8080, '/');
    const service = this.buildService(`${idPrefix}Service`, props, taskDefinition, props.desiredCount, serviceName);
    service.attachToApplicationTargetGroup(targetGroup);

    return { taskDefinition, service, targetGroup, logGroup };
  }

  private buildService(
    id: string,
    props: EcsFargateProps,
    taskDefinition: ecs.FargateTaskDefinition,
    desiredCount: number,
    cloudMapName: string,
    options: { readonly healthCheckGracePeriod?: Duration } = {},
  ): ecs.FargateService {
    return new ecs.FargateService(this, id, {
      cluster: this.cluster,
      taskDefinition,
      desiredCount,
      assignPublicIp: false,
      securityGroups: [props.securityGroup],
      vpcSubnets: { subnetType: props.serviceSubnetType },
      healthCheckGracePeriod: options.healthCheckGracePeriod,
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
      enableExecuteCommand: true,
      circuitBreaker: { rollback: true },
      cloudMapOptions: {
        name: cloudMapName,
      },
    });
  }

  private backendEnvironment(
    props: EcsFargateProps,
    logGroup: logs.LogGroup,
    extra: Record<string, string> = {},
  ): Record<string, string> {
    const dbEndpoint = props.db.dbInstanceEndpointAddress;
    return {
      UPLOAD_DIR: '/app/uploads',
      DATABASE_HOST: dbEndpoint,
      DATABASE_NAME: SAGRILAFT_DB_NAME,
      KEYCLOAK_DB_URL: `jdbc:postgresql://${dbEndpoint}:5432/${SAGRILAFT_DB_NAME}`,
      SNS_TOPIC_ARN: props.alertasTopic.topicArn,
      CW_LOG_GROUP_BACKEND: logGroup.logGroupName,
      MAX_UPLOAD_SIZE_MB: '15',
      GIT_SHA: props.imageTag,
      ...extra,
    };
  }

  private backendSecrets(props: EcsFargateProps, idPrefix: string): Record<string, ecs.Secret> {
    return {
      APP_ENV: this.ssmSecret('APP_ENV', props, idPrefix),
      AWS_REGION: this.ssmSecret('AWS_REGION', props, idPrefix),
      FRONTEND_URL: this.ssmSecret('FRONTEND_URL', props, idPrefix),
      PORTAL_INTERNO_URL: this.ssmSecret('PORTAL_INTERNO_URL', props, idPrefix),
      STORAGE_BACKEND: this.ssmSecret('STORAGE_BACKEND', props, idPrefix),
      S3_BUCKET: this.ssmSecret('S3_BUCKET', props, idPrefix),
      BEDROCK_MODEL_ID: this.ssmSecret('BEDROCK_MODEL_ID', props, idPrefix),
      UVICORN_WORKERS: this.ssmSecret('UVICORN_WORKERS', props, idPrefix),
      TRUSTED_PROXY_IPS: this.ssmSecret('TRUSTED_PROXY_IPS', props, idPrefix),
      PROVEEDOR_LISTAS_CAUTELA: this.ssmSecret('PROVEEDOR_LISTAS_CAUTELA', props, idPrefix),
      SAGRILAFT_API_URL: this.ssmSecret('SAGRILAFT_API_URL', props, idPrefix),
      KEYCLOAK_URL: this.ssmSecret('KEYCLOAK_URL', props, idPrefix),
      KEYCLOAK_REALM: this.ssmSecret('KEYCLOAK_REALM', props, idPrefix),
      KEYCLOAK_CLIENT_ID: this.ssmSecret('KEYCLOAK_CLIENT_ID', props, idPrefix),
      KEYCLOAK_ISSUER_URL: this.ssmSecret('KEYCLOAK_ISSUER_URL', props, idPrefix),
      SMTP_HOST: this.ssmSecret('SMTP_HOST', props, idPrefix),
      SMTP_PORT: this.ssmSecret('SMTP_PORT', props, idPrefix),
      SMTP_FROM: this.ssmSecret('SMTP_FROM', props, idPrefix),
      SES_EMAIL_ORIGEN: this.ssmSecret('SES_EMAIL_ORIGEN', props, idPrefix),
      SES_NOTIFICACIONES_ENABLED: this.ssmSecret('SES_NOTIFICACIONES_ENABLED', props, idPrefix),
      ALERTAS_EMAIL_DESTINATARIO: this.ssmSecret('ALERTAS_EMAIL_DESTINATARIO', props, idPrefix),
      SNS_NOTIFICACIONES_ENABLED: this.ssmSecret('SNS_NOTIFICACIONES_ENABLED', props, idPrefix),
      ZOHO_REDIRECT_URI: this.ssmSecret('ZOHO_REDIRECT_URI', props, idPrefix),
      ZOHO_WEBHOOK_SIGNATURE_HEADER: this.ssmSecret('ZOHO_WEBHOOK_SIGNATURE_HEADER', props, idPrefix),
      ZOHO_SIGN_TESTING: this.ssmSecret('ZOHO_SIGN_TESTING', props, idPrefix),
      ZOHO_REFRESH_MARGIN_SECONDS: this.ssmSecret('ZOHO_REFRESH_MARGIN_SECONDS', props, idPrefix),
      ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS: this.ssmSecret('ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS', props, idPrefix),
      ZOHO_HTTP_MAX_ATTEMPTS: this.ssmSecret('ZOHO_HTTP_MAX_ATTEMPTS', props, idPrefix),
      ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS: this.ssmSecret('ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS', props, idPrefix),
      ZOHO_HTTP_BACKOFF_FACTOR: this.ssmSecret('ZOHO_HTTP_BACKOFF_FACTOR', props, idPrefix),
      ZOHO_TOKEN_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_TOKEN_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_STATUS_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_STATUS_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_CANCEL_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_CANCEL_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_DOWNLOAD_TIMEOUT_SECONDS: this.ssmSecret('ZOHO_DOWNLOAD_TIMEOUT_SECONDS', props, idPrefix),
      ZOHO_SIGN_REQUEST_EXPIRATION_DAYS: this.ssmSecret('ZOHO_SIGN_REQUEST_EXPIRATION_DAYS', props, idPrefix),
      SECRET_KEY: ecs.Secret.fromSecretsManager(props.appSecret, 'secret_key'),
      DB_USER: ecs.Secret.fromSecretsManager(props.dbSecret, 'username'),
      DB_PASSWORD: ecs.Secret.fromSecretsManager(props.dbSecret, 'password'),
      KEYCLOAK_DB_USER: ecs.Secret.fromSecretsManager(props.dbSecret, 'username'),
      KEYCLOAK_DB_PASSWORD: ecs.Secret.fromSecretsManager(props.dbSecret, 'password'),
      ZOHO_CLIENT_ID: ecs.Secret.fromSecretsManager(props.zohoSecret, 'client_id'),
      ZOHO_CLIENT_SECRET: ecs.Secret.fromSecretsManager(props.zohoSecret, 'client_secret'),
      ZOHO_REFRESH_TOKEN: ecs.Secret.fromSecretsManager(props.zohoSecret, 'refresh_token'),
      ZOHO_WEBHOOK_SECRET: ecs.Secret.fromSecretsManager(props.zohoSecret, 'webhook_secret'),
      SMTP_USER: ecs.Secret.fromSecretsManager(props.smtpSecret, 'username'),
      SMTP_PASSWORD: ecs.Secret.fromSecretsManager(props.smtpSecret, 'password'),
      SAGRILAFT_API_KEY: ecs.Secret.fromSecretsManager(props.sagrilaftSecret, 'api_key'),
    };
  }

  private buildExecutionRole(props: EcsFargateProps): iam.Role {
    const role = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    props.grantEcrPull(role);
    props.grantSecretsRead(role);
    this.grantParameterRead(role, props.configParameterNames);

    return role;
  }

  private buildFrontendRole(id: string, props: EcsFargateProps): iam.Role {
    const role = this.buildTaskRole(id);
    this.grantParameterRead(role, props.configParameterNames);
    return role;
  }

  private buildBackendRole(props: EcsFargateProps): iam.Role {
    const role = this.buildTaskRole('BackendTaskRole');

    props.bucket.grantReadWrite(role);
    props.grantSecretsRead(role);
    this.grantParameterRead(role, props.configParameterNames);

    role.addToPolicy(new iam.PolicyStatement({
      sid: 'Ses',
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendRawEmail', 'ses:SendEmail'],
      resources: ['*'],
    }));

    props.alertasTopic.grantPublish(role);
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'SnsHealthCheck',
      effect: iam.Effect.ALLOW,
      actions: ['sns:GetTopicAttributes'],
      resources: [props.alertasTopic.topicArn],
    }));

    role.addToPolicy(new iam.PolicyStatement({
      sid: 'Bedrock',
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: ['*'],
    }));

    role.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudWatchMetrics',
      effect: iam.Effect.ALLOW,
      actions: ['cloudwatch:PutMetricData'],
      resources: ['*'],
      conditions: {
        StringEquals: { 'cloudwatch:namespace': 'SAGRILAFT' },
      },
    }));

    return role;
  }

  private buildKeycloakRole(props: EcsFargateProps): iam.Role {
    const role = this.buildTaskRole('KeycloakTaskRole');
    props.dbSecret.grantRead(role);
    props.keycloakAdminSecret.grantRead(role);
    this.grantParameterRead(role, props.configParameterNames);
    return role;
  }

  private buildTaskRole(id: string): iam.Role {
    return new iam.Role(this, id, {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
  }

  private buildLogGroup(id: string, ambiente: string, service: string, retention: logs.RetentionDays): logs.LogGroup {
    return new logs.LogGroup(this, id, {
      logGroupName: `/sagrilaft/${ambiente}/ecs/${service}`,
      retention,
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }

  private buildTargetGroup(
    id: string,
    props: EcsFargateProps,
    service: string,
    port: number,
    healthPath: string,
  ): elbv2.ApplicationTargetGroup {
    return new elbv2.ApplicationTargetGroup(this, id, {
      vpc: props.vpc,
      targetType: elbv2.TargetType.IP,
      protocol: elbv2.ApplicationProtocol.HTTP,
      port,
      targetGroupName: `sagrilaft-${props.ambiente}-${service}-ecs`,
      deregistrationDelay: Duration.seconds(30),
      healthCheck: {
        path: healthPath,
        healthyHttpCodes: '200-399',
      },
    });
  }

  private ssmSecret(key: string, props: EcsFargateProps, idPrefix = ''): ecs.Secret {
    const parameter = props.configParameterByKey[key];
    if (!parameter) {
      throw new Error(`Parametro SSM no encontrado para ${key}`);
    }

    return ecs.Secret.fromSsmParameter(parameter);
  }

  private grantParameterRead(role: iam.Role, parameterNames: string[]): void {
    role.addToPolicy(new iam.PolicyStatement({
      sid: 'RuntimeConfigParameters',
      effect: iam.Effect.ALLOW,
      actions: ['ssm:GetParameter', 'ssm:GetParameters'],
      resources: parameterNames.map(name =>
        `arn:aws:ssm:${Stack.of(this).region}:${Stack.of(this).account}:parameter${name}`,
      ),
    }));
  }

  private toId(key: string): string {
    return key.toLowerCase().replace(/_/g, '-');
  }
}
