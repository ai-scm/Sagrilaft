import { Duration } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';

export interface LoadBalancerProps {
  readonly vpc: ec2.Vpc;
  readonly securityGroup: ec2.SecurityGroup;
  readonly targetFormularioPublico: elbv2.IApplicationTargetGroup;
  readonly targetPortalInterno: elbv2.IApplicationTargetGroup;
  readonly targetBackend: elbv2.IApplicationTargetGroup;
  readonly targetKeycloak: elbv2.IApplicationTargetGroup;
  readonly certificado: acm.ICertificate;
  readonly dominio: string;
  readonly dominioPortal: string;
  readonly dominioKeycloak: string;
}

/**
 * LoadBalancer: ALB público con enrutamiento basado en host.
 * Los tipos de VPC y Security Group representan red compartida del ALB.
 *
 * Routing:
 *   sagrilaft.dominio.com/api/* → ECS backend
 *   portal.dominio.com/api/*    → ECS backend
 *   sagrilaft.dominio.com  → ECS formulario público
 *   portal.dominio.com     → ECS portal interno
 *   auth.dominio.com       → ECS Keycloak
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
      // 300 s > read_timeout de boto3 (280 s) > tiempo máximo de Bedrock (~90 s).
      // Sin este ajuste el ALB corta la conexión a los 60 s por defecto
      // mientras Bedrock aún procesa el PDF → HTTP 504 en el frontend.
      idleTimeout: Duration.seconds(300),
    });

    // HTTPS listener con enrutamiento por host y 404 por defecto
    const listenerHttps = this.alb.addListener('Https', {
      port: 443,
      certificates: [props.certificado],
      defaultAction: elbv2.ListenerAction.fixedResponse(404, {
        contentType: 'text/plain',
        messageBody: 'No encontrado - SAGRILAFT',
      }),
    });

    listenerHttps.addAction('BackendApiPublica', {
      priority: 1,
      conditions: [
        elbv2.ListenerCondition.hostHeaders([props.dominio]),
        elbv2.ListenerCondition.pathPatterns(['/api/*', '/health']),
      ],
      action: elbv2.ListenerAction.forward([props.targetBackend]),
    });

    listenerHttps.addAction('BackendApiPortal', {
      priority: 2,
      conditions: [
        elbv2.ListenerCondition.hostHeaders([props.dominioPortal]),
        elbv2.ListenerCondition.pathPatterns(['/api/*', '/health']),
      ],
      action: elbv2.ListenerAction.forward([props.targetBackend]),
    });

    listenerHttps.addAction('AppPublica', {
      priority: 5,
      conditions: [elbv2.ListenerCondition.hostHeaders([props.dominio])],
      action: elbv2.ListenerAction.forward([props.targetFormularioPublico]),
    });

    listenerHttps.addAction('PortalInterno', {
      priority: 10,
      conditions: [elbv2.ListenerCondition.hostHeaders([props.dominioPortal])],
      action: elbv2.ListenerAction.forward([props.targetPortalInterno]),
    });

    listenerHttps.addAction('Keycloak', {
      priority: 20,
      conditions: [elbv2.ListenerCondition.hostHeaders([props.dominioKeycloak])],
      action: elbv2.ListenerAction.forward([props.targetKeycloak]),
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
