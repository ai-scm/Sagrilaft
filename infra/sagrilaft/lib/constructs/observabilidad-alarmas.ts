import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cw_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as sns from 'aws-cdk-lib/aws-sns';
import { Duration, Size } from 'aws-cdk-lib';

/** Servicio publicado detrás del ALB que se vigila por sus copias sanas. */
export interface ServicioVigilado {
  /** Nombre corto en español; se usa en el id y en el texto del aviso. */
  readonly nombre: string;
  readonly targetGroup: elbv2.ApplicationTargetGroup;
}

/**
 * Umbrales de la base de datos. Medido del 3 al 16 de noviembre de 2026: CPU promedio
 * 4 % y 11 conexiones como máximo. Los umbrales avisan mucho antes de un problema real.
 */
export const UMBRAL_CPU_BASE_DATOS = 80;
/**
 * db.t3.small admite unas 190 conexiones. Cada copia del backend puede abrir hasta 120
 * (4 procesos x 30), así que 120 ya indica algo anormal (fuga de conexiones o picos).
 */
export const UMBRAL_CONEXIONES_BASE_DATOS = 120;
/** Producción tiene 100 GB de disco; fuera de producción, 20 GB que crecen hasta 50. */
export function umbralEspacioLibreBaseDatos(ambiente: string): Size {
  return ambiente === 'prod' ? Size.gibibytes(10) : Size.gibibytes(2);
}

/**
 * Filtros sobre los registros del backend. El backend solo responde 502 cuando falla
 * Zoho Sign (sin créditos, credenciales o caída del proveedor; ver backend/main.py),
 * y escribe «Error al enviar notificación» cuando un correo a la contraparte no sale.
 */
export const FILTRO_FIRMA_FALLIDA = '[nivel, cliente, guion, peticion, codigo=502, ...]';
export const FILTRO_CORREO_FALLIDO = '"Error al enviar notificación"';

export interface ObservabilidadAlarmasProps {
  /** Balanceador de carga para monitorear errores de la capa de red y ruteo */
  readonly balanceadorCarga: elbv2.ApplicationLoadBalancer;
  
  /** Servicio Backend principal para monitorear consumo de CPU/Memoria */
  readonly servicioBackend: ecs.FargateService;

  /** Topic de notificaciones (SNS) al que están suscritos los ingenieros/soporte */
  readonly topicAlertas: sns.ITopic;

  /** Entorno actual (staging, prod). En staging no despachamos alarmas por defecto para evitar ruido. */
  readonly ambiente: string;

  /** Servicios detrás del ALB (backend, formulario, portal, Keycloak). */
  readonly servicios: ServicioVigilado[];

  /** Base de datos PostgreSQL de la aplicación y de Keycloak. */
  readonly baseDatos: rds.DatabaseInstance;

  /** Registros del backend, de donde salen las métricas de firma y correo fallidos. */
  readonly registrosBackend: logs.ILogGroup;
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
  /** Todas las alarmas, para pruebas y para el tablero. */
  public readonly alarmas: cloudwatch.Alarm[] = [];

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

    this.alarmas.push(alarmaErroresServidor, alarmaSaturacionCpu, alarmaSaturacionMemoria);

    this.crearAlarmasServicios(props);
    this.crearAlarmasBaseDatos(props);
    this.crearAlarmasOperacion(props);

    // Conectar las alarmas al Topic SNS solo si estamos en Producción.
    // Esto evita fatiga de alarmas en Staging donde es normal que los desarrolladores causen errores 500.
    // Cada alarma avisa al entrar en ALARM y otra vez al recuperarse (OK).
    if (esProduccion) {
      for (const alarma of this.alarmas) {
        alarma.addAlarmAction(accionNotificarEquipo);
        alarma.addOkAction(accionNotificarEquipo);
      }
    }
  }

  /**
   * 4. y 5. Copias de cada servicio según el balanceador.
   * - Sin copias sanas durante 3 minutos: el servicio está caído para los usuarios
   *   (si es Keycloak, nadie del equipo interno puede iniciar sesión).
   * - Alguna copia no sana durante 5 minutos: una copia falla sus revisiones de salud;
   *   si hay otra sana el servicio sigue, pero con menos capacidad o un despliegue trabado.
   */
  private crearAlarmasServicios(props: ObservabilidadAlarmasProps): void {
    for (const servicio of props.servicios) {
      const id = servicio.nombre.replace(/(^|-)(\w)/g, (_, __, letra: string) => letra.toUpperCase());

      this.alarmas.push(new cloudwatch.Alarm(this, `AlarmaSinCopiasSanas${id}`, {
        metric: servicio.targetGroup.metrics.healthyHostCount({
          period: Duration.minutes(1),
          statistic: 'Minimum',
        }),
        threshold: 1,
        evaluationPeriods: 3,
        comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        // Sin datos también es grave: el balanceador dejó de informar sobre el servicio.
        treatMissingData: cloudwatch.TreatMissingData.BREACHING,
        alarmDescription:
          `Servicio caído: ${servicio.nombre} lleva 3 minutos sin ninguna copia sana. ` +
          'Los usuarios ven errores. Revisar en ECS por qué se detienen las tareas ' +
          '(eventos del servicio y sus registros) y en el runbook, sección de alarmas.',
      }));

      this.alarmas.push(new cloudwatch.Alarm(this, `AlarmaCopiasNoSanas${id}`, {
        metric: servicio.targetGroup.metrics.unhealthyHostCount({
          period: Duration.minutes(1),
          statistic: 'Maximum',
        }),
        threshold: 1,
        evaluationPeriods: 5,
        comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        alarmDescription:
          `Copia con fallas: ${servicio.nombre} tiene al menos una copia que no pasa la ` +
          'revisión de salud desde hace 5 minutos. Si es durante un despliegue, puede estar ' +
          'trabado; si no, revisar los registros de esa copia.',
      }));
    }
  }

  /** 6., 7. y 8. Base de datos: disco, CPU y conexiones. */
  private crearAlarmasBaseDatos(props: ObservabilidadAlarmasProps): void {
    const umbralDisco = umbralEspacioLibreBaseDatos(props.ambiente);

    this.alarmas.push(new cloudwatch.Alarm(this, 'AlarmaEspacioBaseDatos', {
      metric: props.baseDatos.metricFreeStorageSpace({
        period: Duration.minutes(5),
        statistic: 'Minimum',
      }),
      threshold: umbralDisco.toBytes(),
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.BREACHING,
      // Mismo texto en todos los ambientes: el preflight de deploy_release.py compara
      // las descripciones con tildes contra una lista exacta (APPROVED_UNICODE_PAIRS).
      alarmDescription:
        'Poco disco: a la base de datos le quedan menos de 10 GB libres en producción ' +
        '(2 GB en staging). ' +
        'Si se llena, deja de guardar formularios. Ampliar el disco en RDS (no reinicia) y ' +
        'revisar qué tabla creció.',
    }));

    this.alarmas.push(new cloudwatch.Alarm(this, 'AlarmaCpuBaseDatos', {
      metric: props.baseDatos.metricCPUUtilization({
        period: Duration.minutes(5),
        statistic: 'Average',
      }),
      threshold: UMBRAL_CPU_BASE_DATOS,
      evaluationPeriods: 3,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription:
        `Base de datos saturada: la CPU lleva 15 minutos por encima del ${UMBRAL_CPU_BASE_DATOS} %. ` +
        'Las pantallas se vuelven lentas. Revisar en RDS (Performance Insights) qué consulta la ocupa.',
    }));

    this.alarmas.push(new cloudwatch.Alarm(this, 'AlarmaConexionesBaseDatos', {
      metric: props.baseDatos.metricDatabaseConnections({
        period: Duration.minutes(5),
        statistic: 'Maximum',
      }),
      threshold: UMBRAL_CONEXIONES_BASE_DATOS,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription:
        `Demasiadas conexiones: la base de datos tiene ${UMBRAL_CONEXIONES_BASE_DATOS} o más conexiones ` +
        'abiertas desde hace 10 minutos (lo normal son unas 10). Cerca de 190 empieza a ' +
        'rechazar nuevas. Revisar si alguna copia del backend o Keycloak está atascada.',
    }));
  }

  /** 9. y 10. Firma con Zoho Sign y correo a la contraparte, contados en los registros. */
  private crearAlarmasOperacion(props: ObservabilidadAlarmasProps): void {
    const espacioNombres = `Sagrilaft/Operacion/${props.ambiente}`;

    const firma = new logs.MetricFilter(this, 'FiltroFirmaFallida', {
      logGroup: props.registrosBackend,
      filterPattern: logs.FilterPattern.literal(FILTRO_FIRMA_FALLIDA),
      metricNamespace: espacioNombres,
      metricName: 'FirmaZohoFallida',
      metricValue: '1',
      defaultValue: 0,
    });

    this.alarmas.push(new cloudwatch.Alarm(this, 'AlarmaFirmaFallida', {
      metric: firma.metric({ period: Duration.minutes(5), statistic: 'Sum' }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription:
        'Firma fallida: Zoho Sign rechazó o no respondió al enviar, cancelar o descargar una firma. ' +
        'Causas habituales: la cuenta se quedó sin créditos de API, credenciales vencidas o ' +
        'Zoho caído. El usuario vio el motivo en pantalla. Revisar la cuenta de Zoho y el runbook, sección Zoho.',
    }));

    const correo = new logs.MetricFilter(this, 'FiltroCorreoFallido', {
      logGroup: props.registrosBackend,
      filterPattern: logs.FilterPattern.literal(FILTRO_CORREO_FALLIDO),
      metricNamespace: espacioNombres,
      metricName: 'CorreoContraparteFallido',
      metricValue: '1',
      defaultValue: 0,
    });

    this.alarmas.push(new cloudwatch.Alarm(this, 'AlarmaCorreoFallido', {
      metric: correo.metric({ period: Duration.minutes(5), statistic: 'Sum' }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription:
        'Correo no enviado: falló el envío de un correo a una contraparte (credenciales, ' +
        'devolución, rechazo o reapertura). La contraparte no recibió el aviso. Revisar los ' +
        'registros del backend («Error al enviar notificación») y el estado de SES; reenviar ' +
        'desde el portal si hace falta.',
    }));
  }
}
