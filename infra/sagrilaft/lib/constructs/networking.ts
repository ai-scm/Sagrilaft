import { Stack } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

/**
 * Networking: VPC con subnets públicas/privadas y Security Groups.
 * El modulo CDK de red se usa aqui solo para VPC, subnets, endpoints y SG.
 *
 * Topología:
 *   Internet → ALB (sgAlb, puertos 80/443)
 *     → ECS Fargate (sgEcs, puertos app solo desde ALB)
 *       → RDS (sgRds, puerto 5432 solo desde ECS)
 */
export class Networking extends Construct {
  public readonly vpc: ec2.Vpc;
  public readonly sgAlb: ec2.SecurityGroup;
  public readonly sgEcs: ec2.SecurityGroup;
  public readonly sgRds: ec2.SecurityGroup;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.vpc = new ec2.Vpc(this, 'Vpc', {
      availabilityZones: [`${Stack.of(this).region}a`, `${Stack.of(this).region}b`],
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

    this.sgAlb = new ec2.SecurityGroup(this, 'SgAlb', {
      vpc: this.vpc,
      description: 'ALB',
    });
    this.sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'HTTP');
    this.sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS');

    this.sgEcs = new ec2.SecurityGroup(this, 'SgEcs', {
      vpc: this.vpc,
      description: 'ECS Fargate services',
      allowAllOutbound: true,
    });
    this.sgEcs.addIngressRule(this.sgAlb, ec2.Port.tcp(8080), 'desde ALB to frontends/Keycloak ECS');
    this.sgEcs.addIngressRule(this.sgAlb, ec2.Port.tcp(8000), 'desde ALB to backend ECS');
    this.sgEcs.addIngressRule(this.sgEcs, ec2.Port.tcp(8080), 'trafico interno ECS hacia frontends/Keycloak');
    this.sgEcs.addIngressRule(this.sgEcs, ec2.Port.tcp(8000), 'trafico interno ECS hacia backend');

    this.sgRds = new ec2.SecurityGroup(this, 'SgRds', {
      vpc: this.vpc,
      description: 'RDS postgres',
    });
    this.sgRds.addIngressRule(this.sgEcs, ec2.Port.tcp(5432), 'desde ECS Fargate');

    const sgVpcEndpoints = new ec2.SecurityGroup(this, 'SgVpcEndpoints', {
      vpc: this.vpc,
      description: 'VPC endpoints para ECS Fargate sin NAT',
    });
    sgVpcEndpoints.addIngressRule(this.sgEcs, ec2.Port.tcp(443), 'ECS hacia endpoints privados AWS');
    sgVpcEndpoints.addIngressRule(this.sgEcs, ec2.Port.tcp(587), 'ECS hacia SES SMTP privado');

    this.vpc.addGatewayEndpoint('S3GatewayEndpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_ISOLATED }],
    });

    [
      ['EcrApiEndpoint', ec2.InterfaceVpcEndpointAwsService.ECR],
      ['EcrDockerEndpoint', ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER],
      ['CloudWatchLogsEndpoint', ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS],
      ['SecretsManagerEndpoint', ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER],
      ['SsmEndpoint', ec2.InterfaceVpcEndpointAwsService.SSM],
      ['SsmMessagesEndpoint', ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES],
      ['EcsExecControlChannelEndpoint', ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES],
      ['SesApiEndpoint', ec2.InterfaceVpcEndpointAwsService.EMAIL],
      ['SesSmtpEndpoint', ec2.InterfaceVpcEndpointAwsService.EMAIL_SMTP],
      ['BedrockRuntimeEndpoint', new ec2.InterfaceVpcEndpointService(`com.amazonaws.${Stack.of(this).region}.bedrock-runtime`, 443)],
    ].forEach(([id, service]) => {
      this.vpc.addInterfaceEndpoint(id as string, {
        service: service as ec2.IInterfaceVpcEndpointService,
        open: false,
        securityGroups: [sgVpcEndpoints],
        subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      });
    });
  }
}
