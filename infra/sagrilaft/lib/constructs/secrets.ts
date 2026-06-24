import * as cdk from 'aws-cdk-lib';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export interface SecretsProps {
  readonly ambiente: string;
}

/**
 * Secrets: Credenciales gestionadas por AWS Secrets Manager.
 *
 * Cada secreto es auto-generado o placeholder (REPLACE_ME) según el servicio.
 * El rol del EC2 recibe permisos de lectura (grantRead) desde el stack principal.
 */
export class Secrets extends Construct {
  public readonly dbSecret: secretsmanager.Secret;
  public readonly zohoSecret: secretsmanager.Secret;
  public readonly keycloakAdminSecret: secretsmanager.Secret;
  public readonly smtpSecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props: SecretsProps) {
    super(scope, id);

    const { ambiente } = props;

    this.dbSecret = new secretsmanager.Secret(this, 'DbSecret', {
      secretName: `sagrilaft/${ambiente}/db_password`,
      generateSecretString: {
        secretStringTemplate: '{"username": "sagrilaft_user"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    // ZohoSign: servicio de firma electrónica.
    // El backend usa estas credenciales para:
    //   1. Enviar el PDF del formulario a ZohoSign al aprobar.
    //   2. Recibir el webhook de ZohoSign cuando el firmante completa la firma.
    //   3. Descargar el PDF firmado y almacenarlo en S3.
    // TODO: reemplazar los valores 'REPLACE_ME' con las credenciales reales de ZohoSign
    //       (obtenidas en https://sign.zoho.com → Settings → API).
    this.zohoSecret = new secretsmanager.Secret(this, 'ZohoCredentialsSecret', {
      secretName: `sagrilaft/${ambiente}/zoho_credentials`,
      secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
        client_id:      'REPLACE_ME',  // ZohoSign OAuth client_id
        client_secret:  'REPLACE_ME',  // ZohoSign OAuth client_secret
        refresh_token:  'REPLACE_ME',  // ZohoSign OAuth refresh_token
        webhook_secret: 'REPLACE_ME',  // Secret para validar webhooks entrantes de ZohoSign
      })),
    });

    this.keycloakAdminSecret = new secretsmanager.Secret(this, 'KeycloakAdminSecret', {
      secretName: `sagrilaft/${ambiente}/keycloak_admin_pass`,
      generateSecretString: {
        secretStringTemplate: '{"username": "admin"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    this.smtpSecret = new secretsmanager.Secret(this, 'SmtpCredentialsSecret', {
      secretName: `sagrilaft/${ambiente}/smtp_credentials`,
      generateSecretString: {
        secretStringTemplate: '{"username": "REPLACE_ME"}',
        generateStringKey: 'password',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });
  }

  /** Otorga permisos de lectura de todos los secretos a un rol IAM. */
  public grantReadAll(grantee: cdk.aws_iam.IGrantable): void {
    this.dbSecret.grantRead(grantee);
    this.zohoSecret.grantRead(grantee);
    this.keycloakAdminSecret.grantRead(grantee);
    this.smtpSecret.grantRead(grantee);
  }
}
