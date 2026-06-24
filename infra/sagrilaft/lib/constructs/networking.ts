import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

/**
 * Networking: VPC con subnets públicas/privadas y Security Groups.
 *
 * Topología:
 *   Internet → ALB (sgAlb, puertos 80/443)
 *     → EC2 (sgEc2, puertos 80/81/8080 solo desde ALB)
 *       → RDS (sgRds, puerto 5432 solo desde EC2)
 */
export class Networking extends Construct {
  public readonly vpc: ec2.Vpc;
  public readonly sgAlb: ec2.SecurityGroup;
  public readonly sgEc2: ec2.SecurityGroup;
  public readonly sgRds: ec2.SecurityGroup;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.vpc = new ec2.Vpc(this, 'Vpc', {
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

    this.sgAlb = new ec2.SecurityGroup(this, 'SgAlb', {
      vpc: this.vpc,
      description: 'ALB',
    });
    this.sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'HTTP');
    this.sgAlb.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS');

    this.sgEc2 = new ec2.SecurityGroup(this, 'SgEc2', {
      vpc: this.vpc,
      description: 'EC2 app',
    });
    this.sgEc2.addIngressRule(this.sgAlb, ec2.Port.tcp(80), 'desde ALB -> frontend');
    this.sgEc2.addIngressRule(this.sgAlb, ec2.Port.tcp(81), 'desde ALB -> portal interno');
    this.sgEc2.addIngressRule(this.sgAlb, ec2.Port.tcp(8080), 'desde ALB -> Keycloak');

    this.sgRds = new ec2.SecurityGroup(this, 'SgRds', {
      vpc: this.vpc,
      description: 'RDS postgres',
    });
    this.sgRds.addIngressRule(this.sgEc2, ec2.Port.tcp(5432), 'desde EC2');
  }
}
