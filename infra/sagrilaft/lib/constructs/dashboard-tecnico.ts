import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as rds from 'aws-cdk-lib/aws-rds';

export interface DashboardTecnicoProps {
  balanceadorCarga: elbv2.ApplicationLoadBalancer;
  servicioBackend: ecs.FargateService;
  servicioPortal: ecs.FargateService;
  dbInstance: rds.DatabaseInstance;
  ambiente: string;
}

export class DashboardTecnico extends Construct {
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: DashboardTecnicoProps) {
    super(scope, id);

    this.dashboard = new cloudwatch.Dashboard(this, 'DashboardTecnico', {
      dashboardName: `Sagrilaft-Operativo-${props.ambiente}`,
    });

    // Fila 1: Red y Seguridad (ALB Errors)
    const widgetAlbErrors = new cloudwatch.GraphWidget({
      title: 'ALB: Errores HTTP 5xx y 4xx',
      left: [
        props.balanceadorCarga.metrics.httpCodeTarget(elbv2.HttpCodeTarget.TARGET_5XX_COUNT, { statistic: 'Sum' }),
        props.balanceadorCarga.metrics.httpCodeTarget(elbv2.HttpCodeTarget.TARGET_4XX_COUNT, { statistic: 'Sum' })
      ],
      width: 12
    });

    const widgetAlbLatency = new cloudwatch.GraphWidget({
      title: 'ALB: Latencia de Respuesta',
      left: [
        props.balanceadorCarga.metrics.targetResponseTime({ statistic: 'Average' }),
        props.balanceadorCarga.metrics.targetResponseTime({ statistic: 'Maximum' })
      ],
      width: 12
    });

    this.dashboard.addWidgets(widgetAlbErrors, widgetAlbLatency);

    // Fila 2: Computo (Fargate)
    const widgetCpu = new cloudwatch.GraphWidget({
      title: 'Fargate: Uso de CPU (%)',
      left: [
        props.servicioBackend.metricCpuUtilization({ statistic: 'Average', label: 'Backend CPU' }),
        props.servicioPortal.metricCpuUtilization({ statistic: 'Average', label: 'Portal CPU' })
      ],
      width: 12
    });

    const widgetMem = new cloudwatch.GraphWidget({
      title: 'Fargate: Uso de Memoria (%)',
      left: [
        props.servicioBackend.metricMemoryUtilization({ statistic: 'Average', label: 'Backend Mem' }),
        props.servicioPortal.metricMemoryUtilization({ statistic: 'Average', label: 'Portal Mem' })
      ],
      width: 12
    });

    this.dashboard.addWidgets(widgetCpu, widgetMem);

    // Fila 3: Persistencia (RDS)
    const widgetDbConn = new cloudwatch.GraphWidget({
      title: 'RDS: Conexiones Activas',
      left: [
        props.dbInstance.metricDatabaseConnections({ statistic: 'Average' })
      ],
      width: 12
    });

    const widgetDbCpu = new cloudwatch.GraphWidget({
      title: 'RDS: Uso de CPU (%)',
      left: [
        props.dbInstance.metricCPUUtilization({ statistic: 'Average' })
      ],
      width: 12
    });

    this.dashboard.addWidgets(widgetDbConn, widgetDbCpu);

    // Fila 4: Logs Insights
    const logGroup = `/ecs/sagrilaft-${props.ambiente}-backend`;
    const widgetLogs = new cloudwatch.LogQueryWidget({
      title: 'Buscador de Errores (Logs)',
      logGroupNames: [logGroup],
      view: cloudwatch.LogQueryVisualizationType.TABLE,
      queryLines: [
        'fields @timestamp, request_id, level, message',
        'filter level = "ERROR"',
        'sort @timestamp desc',
        'limit 20'
      ],
      width: 24
    });

    this.dashboard.addWidgets(widgetLogs);
  }
}
