import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cw_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as sns from 'aws-cdk-lib/aws-sns';
import { Duration } from 'aws-cdk-lib';

export interface ObservabilidadAlarmasProps {
  /** Balanceador de carga para monitorear errores de la capa de red y ruteo */
  readonly balanceadorCarga: elbv2.ApplicationLoadBalancer;
  
  /** Servicio Backend principal para monitorear consumo de CPU/Memoria */
  readonly servicioBackend: ecs.FargateService;

  /** Topic de notificaciones (SNS) al que están suscritos los ingenieros/soporte */
  readonly topicAlertas: sns.ITopic;

  /** Entorno actual (staging, prod). En staging no despachamos alarmas por defecto para evitar ruido. */
  readonly ambiente: string;
}

/**
 * ObservabilidadAlarmas: Centraliza la creación de alarmas críticas (MVP)
 * para garantizar la salud y disponibilidad del sistema en Producción.
 * 
 * Principios SOLID: 
 * - Single Responsibility: Solo se encarga de definir métricas y lanzar notificaciones.
 * Lenguaje Ubicuo: 
 * - Nombres claros en español que reflejan el propósito de negocio (ej. AlarmaErroresServidor).
 */
export class ObservabilidadAlarmas extends Construct {
  constructor(scope: Construct, id: string, props: ObservabilidadAlarmasProps) {
    super(scope, id);

    const accionNotificarEquipo = new cw_actions.SnsAction(props.topicAlertas);
    const esProduccion = props.ambiente === 'prod';

    // 1. Alarma de Errores 5xx del Load Balancer (Indicador crítico de caída)
    const metricaErrores5xx = props.balanceadorCarga.metrics.httpCodeTarget(
      elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
      { period: Duration.minutes(5), statistic: 'Sum' }
    );

    const alarmaErroresServidor = new cloudwatch.Alarm(this, 'AlarmaErroresServidor', {
      metric: metricaErrores5xx,
      threshold: 5,
      evaluationPeriods: 1, // 1 periodo de 5 minutos
      alarmDescription: 'Alarma Crítica: Se detectaron más de 5 errores HTTP 5xx en el servidor backend durante los últimos 5 minutos.',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // 2. Alarma de Uso de CPU del Backend
    const metricaCpuBackend = props.servicioBackend.metricCpuUtilization({
      period: Duration.minutes(5),
      statistic: 'Average',
    });

    const alarmaSaturacionCpu = new cloudwatch.Alarm(this, 'AlarmaSaturacionCpu', {
      metric: metricaCpuBackend,
      threshold: 85,
      evaluationPeriods: 1,
      alarmDescription: 'Alarma de Rendimiento: El uso de CPU del servicio Backend superó el 85% de su capacidad.',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // 3. Alarma de Uso de Memoria del Backend
    const metricaMemoriaBackend = props.servicioBackend.metricMemoryUtilization({
      period: Duration.minutes(5),
      statistic: 'Average',
    });

    const alarmaSaturacionMemoria = new cloudwatch.Alarm(this, 'AlarmaSaturacionMemoria', {
      metric: metricaMemoriaBackend,
      threshold: 85,
      evaluationPeriods: 1,
      alarmDescription: 'Alarma de Rendimiento: El uso de Memoria RAM del servicio Backend superó el 85% de su capacidad.',
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Conectar las alarmas al Topic SNS solo si estamos en Producción.
    // Esto evita fatiga de alarmas en Staging donde es normal que los desarrolladores causen errores 500.
    if (esProduccion) {
      alarmaErroresServidor.addAlarmAction(accionNotificarEquipo);
      alarmaErroresServidor.addOkAction(accionNotificarEquipo); // Notificar cuando se recupere

      alarmaSaturacionCpu.addAlarmAction(accionNotificarEquipo);
      alarmaSaturacionCpu.addOkAction(accionNotificarEquipo);

      alarmaSaturacionMemoria.addAlarmAction(accionNotificarEquipo);
      alarmaSaturacionMemoria.addOkAction(accionNotificarEquipo);
    }
  }
}
