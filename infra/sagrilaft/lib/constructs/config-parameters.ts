import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export interface ConfigParametersProps {
  readonly ambiente: string;
  readonly dominio: string;
  readonly dominioPortal: string;
  readonly dominioKeycloak: string;
  readonly s3BucketName: string;
  readonly sesEmailOrigen: string;
  readonly alertasEmailDestino: string;
  readonly bedrockModelId: string;
  readonly sagrilaftApiUrl: string;
}

export class ConfigParameters extends Construct {
  public readonly parameterNames: string[];
  public readonly parameterNameByKey: Record<string, string>;
  public readonly parameterByKey: Record<string, ssm.IStringParameter>;

  constructor(scope: Construct, id: string, props: ConfigParametersProps) {
    super(scope, id);

    const prefix = `/sagrilaft/${props.ambiente}`;
    const values: Record<string, string> = {
      APP_ENV: props.ambiente === 'prod' ? 'production' : props.ambiente,
      AWS_REGION: 'us-east-1',
      FRONTEND_URL: `https://${props.dominio},https://${props.dominioPortal}`,
      PORTAL_INTERNO_URL: `https://${props.dominioPortal}`,
      STORAGE_BACKEND: 's3',
      S3_BUCKET: props.s3BucketName,
      BEDROCK_MODEL_ID: props.bedrockModelId,
      KEYCLOAK_URL: `http://keycloak.sagrilaft-${props.ambiente}.local:8080`,
      KEYCLOAK_REALM: 'sagrilaft',
      KEYCLOAK_CLIENT_ID: 'sagrilaft-portal',
      KEYCLOAK_ISSUER_URL: `https://${props.dominioKeycloak}`,
      KEYCLOAK_HOSTNAME: props.dominioKeycloak,
      VITE_PORTAL_INTERNO_URL: `https://${props.dominioPortal}`,
      VITE_KEYCLOAK_URL: `https://${props.dominioKeycloak}`,
      VITE_KEYCLOAK_REALM: 'sagrilaft',
      VITE_KEYCLOAK_CLIENT_ID: 'sagrilaft-portal',
      SMTP_HOST: 'email-smtp.us-east-1.amazonaws.com',
      SMTP_PORT: '587',
      SMTP_FROM: props.sesEmailOrigen,
      SES_EMAIL_ORIGEN: props.sesEmailOrigen,
      SES_NOTIFICACIONES_ENABLED: 'true',
      ALERTAS_EMAIL_DESTINATARIO: props.alertasEmailDestino,
      SNS_NOTIFICACIONES_ENABLED: 'false',
      ZOHO_REDIRECT_URI: `https://${props.dominioPortal}/oauth/zoho/callback`,
      ZOHO_WEBHOOK_SIGNATURE_HEADER: 'X-ZS-WEBHOOK-SIGNATURE',
      ZOHO_SIGN_TESTING: ['staging', 'prod'].includes(props.ambiente) ? 'false' : 'true',
      UVICORN_WORKERS: '4',
      TRUSTED_PROXY_IPS: '172.0.0.0/8',
      // Produccion y staging deben verificar contra la API real de listas de
      // cautela (tusdatos.co) - nunca el proveedor simulado. Ver validacion
      // de arranque en backend/infrastructure/configuracion.py::load_config().
      PROVEEDOR_LISTAS_CAUTELA: 'sagrilaft',
      SAGRILAFT_API_URL: props.sagrilaftApiUrl,
    };

    this.parameterNameByKey = {};
    this.parameterByKey = {};
    this.parameterNames = Object.entries(values).map(([key, value]) => {
      const parameter = new ssm.StringParameter(this, this.toId(key), {
        parameterName: `${prefix}/config/${key}`,
        stringValue: value,
        description: `SAGRILAFT ${props.ambiente} runtime config: ${key}`,
      });
      this.parameterNameByKey[key] = parameter.parameterName;
      this.parameterByKey[key] = parameter;
      return parameter.parameterName;
    });
  }

  private toId(key: string): string {
    return `${key.toLowerCase().replace(/_/g, '-')}Param`;
  }
}
