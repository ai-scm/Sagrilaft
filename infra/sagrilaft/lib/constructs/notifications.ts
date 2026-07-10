import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as ses from 'aws-cdk-lib/aws-ses';
import { Construct } from 'constructs';

export interface NotificationsProps {
  readonly ambiente: string;
  /** Email verificado como remitente en SES. */
  readonly sesEmailOrigen: string;
  /** Email del equipo de analistas que se suscribe al topic SNS. */
  readonly snsAlertasSub: string;
}

/**
 * Notifications: Identidad SES + Topic SNS para alertas internas.
 *
 * SES: Crea automáticamente la identidad del remitente. AWS enviará un correo
 * de verificación al email configurado.
 *
 * SNS: Crea el topic de alertas y suscribe automáticamente al correo del equipo.
 * AWS enviará un correo de confirmación que debe aceptarse para activar la suscripción.
 */
export class Notifications extends Construct {
  public readonly sesIdentity: ses.EmailIdentity;
  public readonly alertasTopic: sns.Topic;

  constructor(scope: Construct, id: string, props: NotificationsProps) {
    super(scope, id);

    const { ambiente, sesEmailOrigen, snsAlertasSub } = props;

    this.sesIdentity = new ses.EmailIdentity(this, 'SesIdentity', {
      identity: ses.Identity.email(sesEmailOrigen),
    });

    this.alertasTopic = new sns.Topic(this, 'AlertasTopic', {
      displayName: `Sagrilaft Alertas (${ambiente})`,
      topicName: `sagrilaft-alertas-${ambiente}`,
    });

    snsAlertasSub
      .split(',')
      .map((email) => email.trim())
      .filter((email) => email.length > 0)
      .forEach((email) => {
        this.alertasTopic.addSubscription(
          new subscriptions.EmailSubscription(email, {
            json: false,
          }),
        );
      });
  }
}
