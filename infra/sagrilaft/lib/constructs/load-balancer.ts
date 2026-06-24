import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as targets from 'aws-cdk-lib/aws-elasticloadbalancingv2-targets';
import { Construct } from 'constructs';

export interface LoadBalancerProps {
  readonly vpc: ec2.Vpc;
  readonly securityGroup: ec2.SecurityGroup;
  readonly ec2Instance: ec2.Instance;
  readonly certificado: acm.ICertificate;
  readonly dominioPortal: string;
  readonly dominioKeycloak: string;
}

/**
 * LoadBalancer: ALB público con enrutamiento basado en host.
 *
 * Routing:
 *   sagrilaft.dominio.com  → EC2:80  (formulario público)
 *   portal.dominio.com     → EC2:81  (portal interno)
 *   auth.dominio.com       → EC2:8080 (Keycloak)
 *
 * HTTP:80 redirige permanentemente a HTTPS:443.
 */
export class LoadBalancer extends Construct {
  public readonly alb: elbv2.ApplicationLoadBalancer;

  constructor(scope: Construct, id: string, props: LoadBalancerProps) {
    super(scope, id);

    this.alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc: props.vpc,
      internetFacing: true,
      securityGroup: props.securityGroup,
    });

    const targetApp = new elbv2.ApplicationTargetGroup(this, 'TgApp', {
      vpc: props.vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(props.ec2Instance.instanceId, 80)],
      healthCheck: { path: '/', healthyHttpCodes: '200-299' },
    });

    const targetPortal = new elbv2.ApplicationTargetGroup(this, 'TgPortal', {
      vpc: props.vpc,
      port: 81,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(props.ec2Instance.instanceId, 81)],
      healthCheck: { path: '/', healthyHttpCodes: '200-299' },
    });

    const targetKc = new elbv2.ApplicationTargetGroup(this, 'TgKeycloak', {
      vpc: props.vpc,
      port: 8080,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [new targets.InstanceIdTarget(props.ec2Instance.instanceId, 8080)],
      healthCheck: { path: '/realms/sagrilaft', healthyHttpCodes: '200-299' },
    });

    // HTTPS listener con enrutamiento por host
    const listenerHttps = this.alb.addListener('Https', {
      port: 443,
      certificates: [props.certificado],
      defaultTargetGroups: [targetApp],
    });

    listenerHttps.addAction('PortalInterno', {
      priority: 10,
      conditions: [elbv2.ListenerCondition.hostHeaders([props.dominioPortal])],
      action: elbv2.ListenerAction.forward([targetPortal]),
    });

    listenerHttps.addAction('Keycloak', {
      priority: 20,
      conditions: [elbv2.ListenerCondition.hostHeaders([props.dominioKeycloak])],
      action: elbv2.ListenerAction.forward([targetKc]),
    });

    // HTTP → HTTPS redirect permanente
    this.alb.addListener('Http', {
      port: 80,
      defaultAction: elbv2.ListenerAction.redirect({
        protocol: 'HTTPS',
        port: '443',
        permanent: true,
      }),
    });
  }
}
