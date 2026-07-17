import { Construct } from 'constructs';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';

export interface CortafuegosWebProps {
  /**
   * ARN del Application Load Balancer al cual se adjuntará el firewall web.
   */
  readonly arnBalanceadorCarga: string;
}

/**
 * CortafuegosWeb: Implementa las defensas perimetrales esenciales para proteger 
 * la aplicación SAGRILAFT de tráfico malicioso.
 * 
 * Principios SOLID: 
 * - Single Responsibility: Solo se encarga de definir y asociar reglas WAF.
 * Lenguaje Ubicuo: 
 * - Se nombran las reglas y constructos reflejando la intención de negocio (ej. EntradasMaliciosasConocidas).
 */
export class CortafuegosWeb extends Construct {
  constructor(scope: Construct, id: string, props: CortafuegosWebProps) {
    super(scope, id);

    // 1. Definición del WebACL con la acción por defecto de Permitir (Allow)
    const aclSagrilaft = new wafv2.CfnWebACL(this, 'AclSagrilaft', {
      defaultAction: { allow: {} },
      scope: 'REGIONAL', // Para Application Load Balancer debe ser REGIONAL
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: 'SagrilaftCortafuegosGeneral',
        sampledRequestsEnabled: true,
      },
      rules: [
        // Regla 1: Core Rule Set (Protección contra vulnerabilidades comunes web como SQLi, XSS)
        {
          name: 'ProteccionVulnerabilidadesComunes',
          priority: 1,
          overrideAction: { none: {} }, // 'none' significa que aplicamos la acción de la regla gestionada (Block)
          statement: {
            managedRuleGroupStatement: {
              name: 'AWSManagedRulesCommonRuleSet',
              vendorName: 'AWS',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'ProteccionVulnerabilidadesComunesMetrica',
            sampledRequestsEnabled: true,
          },
        },
        // Regla 2: Known Bad Inputs (Bloqueo de IPs maliciosas conocidas, botnets, escáneres)
        {
          name: 'BloqueoEntradasMaliciosasConocidas',
          priority: 2,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              name: 'AWSManagedRulesKnownBadInputsRuleSet',
              vendorName: 'AWS',
            },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: 'BloqueoEntradasMaliciosasConocidasMetrica',
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    // 2. Asociación del WebACL al Application Load Balancer
    new wafv2.CfnWebACLAssociation(this, 'AsociacionAlb', {
      resourceArn: props.arnBalanceadorCarga,
      webAclArn: aclSagrilaft.attrArn,
    });
  }
}
