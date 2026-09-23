import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as ses from 'aws-cdk-lib/aws-ses';
import { Construct } from 'constructs';

export interface NotificationsProps {
  readonly ambiente: string;
  /** Email verificado como remitente en SES (usado solo si no hay dominioSesVerificado). */
  readonly sesEmailOrigen: string;
  /**
   * Dominio ya verificado en SES por fuera de este stack (con DKIM
   * habilitado), ej. 'ia.blend360.com'. Si se provee, SE IMPORTA la
   * identidad existente (nunca se crea vía CDK): la identidad de dominio es
   * un recurso único por cuenta+región y ya fue verificada manualmente, así
   * que CloudFormation no debe intentar "crearla" (falla con AlreadyExists).
   */
  readonly dominioSesVerificado?: string;
  /** Email del equipo de analistas que se suscribe al topic SNS. */
  readonly snsAlertasSub: string;
}

/**
 * Notifications: Identidad SES + Topic SNS para alertas internas.
 *
 * SES: si hay dominioSesVerificado, importa esa identidad de dominio ya
 * verificada (con DKIM) sin intentar crearla. Sin dominioSesVerificado, cae
 * a verificar solo la dirección de correo individual (requiere abrir el
 * link de verificación que AWS envía a ese correo).
 *
 * SNS: Crea el topic de alertas y suscribe automáticamente al correo del equipo.
 * AWS enviará un correo de confirmación que debe aceptarse para activar la suscripción.
 */
export class Notifications extends Construct {
  public readonly sesIdentity: ses.IEmailIdentity;
  public readonly alertasTopic: sns.Topic;

  constructor(scope: Construct, id: string, props: NotificationsProps) {
    super(scope, id);

    const { ambiente, sesEmailOrigen, dominioSesVerificado, snsAlertasSub } = props;

    this.sesIdentity = dominioSesVerificado
      ? ses.EmailIdentity.fromEmailIdentityName(this, 'SesIdentity', dominioSesVerificado)
      : new ses.EmailIdentity(this, 'SesIdentity', {
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
