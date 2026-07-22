import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cdk from 'aws-cdk-lib';

export interface DashboardNegocioProps {
  ambiente: string;
}

export class DashboardNegocio extends Construct {
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: DashboardNegocioProps) {
    super(scope, id);

    this.dashboard = new cloudwatch.Dashboard(this, 'DashboardNegocio', {
      dashboardName: `Sagrilaft-Negocio-${props.ambiente}`,
    });

    // Fila 1: Embudo de Aprobación
    const widgetEmbudo = new cloudwatch.GraphWidget({
      title: 'Tasas de Éxito: Decisiones de Expedientes',
      view: cloudwatch.GraphWidgetView.BAR,
      left: [
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'ExpedientesProcesados',
          dimensionsMap: { Embudo: 'Aprobado' },
          statistic: 'Sum',
          period: cdk.Duration.days(1),
          label: 'Aprobados'
        }),
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'ExpedientesProcesados',
          dimensionsMap: { Embudo: 'Devuelto' },
          statistic: 'Sum',
          period: cdk.Duration.days(1),
          label: 'Devueltos'
        }),
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'ExpedientesProcesados',
          dimensionsMap: { Embudo: 'Rechazado' },
          statistic: 'Sum',
          period: cdk.Duration.days(1),
          label: 'Rechazados'
        })
      ],
      width: 24
    });

    this.dashboard.addWidgets(widgetEmbudo);

    // Fila 2: Costos de IA (Tokens Bedrock)
    const widgetBedrock = new cloudwatch.GraphWidget({
      title: 'Amazon Bedrock: Consumo de Tokens',
      view: cloudwatch.GraphWidgetView.TIME_SERIES,
      stacked: true,
      left: [
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'BedrockInputTokens',
          dimensionsMap: { Servicio: 'Bedrock' },
          statistic: 'Sum'
        }),
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'BedrockOutputTokens',
          dimensionsMap: { Servicio: 'Bedrock' },
          statistic: 'Sum'
        })
      ],
      width: 24
    });

    this.dashboard.addWidgets(widgetBedrock);

    // Fila 3: SLAs de Proveedores (Latencia)
    const widgetSla = new cloudwatch.GraphWidget({
      title: 'SLA Integraciones: Latencia Promedio (ms)',
      left: [
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'TusDatosLatency',
          dimensionsMap: { Servicio: 'TusDatos' },
          statistic: 'Average'
        }),
        new cloudwatch.Metric({
          namespace: 'Sagrilaft/Negocio',
          metricName: 'ZohoSignLatency',
          dimensionsMap: { Servicio: 'ZohoSign' },
          statistic: 'Average'
        })
      ],
      width: 24
    });

    this.dashboard.addWidgets(widgetSla);
  }
}
