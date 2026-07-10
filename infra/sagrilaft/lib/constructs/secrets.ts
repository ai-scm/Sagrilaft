  import * as cdk from 'aws-cdk-lib';
  import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
  import { Construct } from 'constructs';

  export interface SecretsProps {
    readonly ambiente: string;
  }

  /**
   * Secrets: Credenciales gestionadas por AWS Secrets Manager.
   *
   * Los secretos generados nacen con valores seguros; los secretos de integraciones
   * externas nacen vacios y deben rellenarse en Secrets Manager antes del deploy app.
   * Los roles ECS reciben permisos de lectura (grantRead) desde el stack principal.
   */
  export class Secrets extends Construct {
    public readonly dbSecret: secretsmanager.Secret;
    public readonly appSecret: secretsmanager.Secret;
    public readonly zohoSecret: secretsmanager.Secret;
    public readonly keycloakAdminSecret: secretsmanager.Secret;
    public readonly smtpSecret: secretsmanager.Secret;

    constructor(scope: Construct, id: string, props: SecretsProps) {
      super(scope, id);

      const { ambiente } = props;

      this.dbSecret = new secretsmanager.Secret(this, 'DbSecret', {
        secretName: `sagrilaft/${ambiente}/db_credentials`,
        generateSecretString: {
          secretStringTemplate: '{"username": "sagrilaft_user"}',
          generateStringKey: 'password',
          excludePunctuation: true,
          passwordLength: 32,
        },
      });

      this.appSecret = new secretsmanager.Secret(this, 'AppSecret', {
        secretName: `sagrilaft/${ambiente}/app_secret`,
        generateSecretString: {
          secretStringTemplate: '{}',
          generateStringKey: 'secret_key',
          excludePunctuation: true,
          passwordLength: 64,
        },
      });

      this.zohoSecret = new secretsmanager.Secret(this, 'ZohoCredentialsSecret', {
        secretName: `sagrilaft/${ambiente}/zoho_credentials`,
        secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
          client_id: '',
          client_secret: '',
          refresh_token: '',
          webhook_secret: '',
        })),
      });

      this.keycloakAdminSecret = new secretsmanager.Secret(this, 'KeycloakAdminSecret', {
        secretName: `sagrilaft/${ambiente}/keycloak_admin`,
        generateSecretString: {
          secretStringTemplate: '{"username": "admin"}',
          generateStringKey: 'password',
          excludePunctuation: true,
          passwordLength: 32,
        },
      });

      this.smtpSecret = new secretsmanager.Secret(this, 'SmtpCredentialsSecret', {
        secretName: `sagrilaft/${ambiente}/smtp_credentials`,
        secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
          username: '',
          password: '',
        })),
      });
    }

    /** Otorga permisos de lectura de todos los secretos a un rol IAM. */
    public grantReadAll(grantee: cdk.aws_iam.IGrantable): void {
      this.dbSecret.grantRead(grantee);
      this.appSecret.grantRead(grantee);
      this.zohoSecret.grantRead(grantee);
      this.keycloakAdminSecret.grantRead(grantee);
      this.smtpSecret.grantRead(grantee);
    }
  }
