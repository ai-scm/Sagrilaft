import * as route53 from 'aws-cdk-lib/aws-route53';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as ses from 'aws-cdk-lib/aws-ses';
import { Construct } from 'constructs';

export interface NotificationsProps {
  readonly ambiente: string;
  /** Email verificado como remitente en SES (usado solo si no hay hostedZone). */
  readonly sesEmailOrigen: string;
  /**
   * Hosted zone pública sobre la que vive sesEmailOrigen. Si se provee, SES
   * verifica el DOMINIO completo (no solo el correo) y crea automáticamente
   * los registros DKIM y MAIL FROM en esa zona, habilitando autenticación
   * real (DKIM+SPF) para cualquier dirección de ese dominio.
   */
  readonly hostedZone?: route53.IPublicHostedZone;
  /**
   * Si este stack es el "dueño" de la identidad de dominio SES (crea el
   * recurso CDK con DKIM + MAIL FROM). Una identidad de dominio es única por
   * cuenta+región de AWS, no por ambiente: si dos stacks (ej. staging y prod)
   * la crean cada uno por su lado, colisionan en el despliegue y destruir uno
   * de los stacks borraría la identidad que usa el otro. Solo un stack debe
   * tener este flag en true; los demás importan la identidad ya creada.
   */
  readonly esDuenoIdentidadSes: boolean;
  /** Email del equipo de analistas que se suscribe al topic SNS. */
  readonly snsAlertasSub: string;
}

/**
 * Notifications: Identidad SES + Topic SNS para alertas internas.
 *
 * SES: si hay hostedZone y este stack es el dueño (esDuenoIdentidadSes),
 * verifica el DOMINIO completo y crea DKIM + MAIL FROM automáticamente en
 * Route53 (sin correo de verificación manual). Si hay hostedZone pero este
 * stack no es el dueño, importa la identidad de dominio ya creada por el
 * stack dueño (mismo dominio, sin duplicar el recurso). Sin hostedZone, cae
 * a verificar solo la dirección de correo (requiere abrir el link de
 * verificación que AWS envía a ese correo).
 *
 * SNS: Crea el topic de alertas y suscribe automáticamente al correo del equipo.
 * AWS enviará un correo de confirmación que debe aceptarse para activar la suscripción.
 */
export class Notifications extends Construct {
  public readonly sesIdentity: ses.IEmailIdentity;
  public readonly alertasTopic: sns.Topic;

  constructor(scope: Construct, id: string, props: NotificationsProps) {
    super(scope, id);

    const { ambiente, sesEmailOrigen, hostedZone, esDuenoIdentidadSes, snsAlertasSub } = props;

    if (hostedZone && esDuenoIdentidadSes) {
      this.sesIdentity = new ses.EmailIdentity(this, 'SesIdentity', {
        identity: ses.Identity.publicHostedZone(hostedZone),
        // Subdominio dedicado para el "envelope sender": alinea SPF con el
        // dominio del remitente (requisito para DMARC alignment).
        mailFromDomain: `mail.${hostedZone.zoneName}`,
      });
    } else if (hostedZone) {
      this.sesIdentity = ses.EmailIdentity.fromEmailIdentityName(
        this, 'SesIdentity', hostedZone.zoneName,
      );
    } else {
      this.sesIdentity = new ses.EmailIdentity(this, 'SesIdentity', {
        identity: ses.Identity.email(sesEmailOrigen),
      });
    }

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
