import { RemovalPolicy } from 'aws-cdk-lib';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface ObservabilityProps {
  readonly ambiente: string;
}

/**
 * Observability: CloudWatch Log Groups con retención diferenciada.
 *
 * Cada contenedor Docker envía sus logs al Log Group correspondiente
 * via el driver awslogs (configurado en docker-compose.prod.yml).
 * El CloudWatch Agent captura los logs del bootstrap del EC2.
 *
 * Retención por criticidad:
 *   backend   : 1 mes  ← logs de negocio (formularios, IA, errores críticos)
 *   keycloak  : 2 sem  ← eventos de autenticación
 *   frontends : 2 sem  ← errores de Nginx (poco volumen)
 *   bootstrap : 1 sem  ← solo útil para diagnóstico post-deploy
 */
export class Observability extends Construct {
  public readonly lgBackend: logs.LogGroup;
  public readonly lgFrontend: logs.LogGroup;
  public readonly lgPortal: logs.LogGroup;
  public readonly lgKeycloak: logs.LogGroup;
  public readonly lgBootstrap: logs.LogGroup;

  constructor(scope: Construct, id: string, props: ObservabilityProps) {
    super(scope, id);

    const { ambiente } = props;

    this.lgBackend = new logs.LogGroup(this, 'LogGroupBackend', {
      logGroupName: `/sagrilaft/${ambiente}/backend`,
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.lgFrontend = new logs.LogGroup(this, 'LogGroupFrontend', {
      logGroupName: `/sagrilaft/${ambiente}/frontend`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.lgPortal = new logs.LogGroup(this, 'LogGroupPortal', {
      logGroupName: `/sagrilaft/${ambiente}/portal`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.lgKeycloak = new logs.LogGroup(this, 'LogGroupKeycloak', {
      logGroupName: `/sagrilaft/${ambiente}/keycloak`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.lgBootstrap = new logs.LogGroup(this, 'LogGroupBootstrap', {
      logGroupName: `/sagrilaft/${ambiente}/bootstrap`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }

  /** Retorna todos los ARNs (grupo + streams) para políticas IAM. */
  public get allLogGroupArns(): string[] {
    const groups = [
      this.lgBackend, this.lgFrontend, this.lgPortal,
      this.lgKeycloak, this.lgBootstrap,
    ];
    return groups.flatMap(g => [g.logGroupArn, `${g.logGroupArn}:*`]);
  }
}
