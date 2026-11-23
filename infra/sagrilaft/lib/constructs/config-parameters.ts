import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { DEFAULT_REGION } from '../deployment-constants';

export interface ConfigParametersProps {
  readonly ambiente: string;
  readonly dominio: string;
  readonly dominioPortal: string;
  readonly dominioKeycloak: string;
  readonly s3BucketName: string;
  readonly sesEmailOrigen: string;
  readonly smtpReplyTo: string;
  readonly alertasEmailDestino: string;
  readonly bedrockModelId: string;
  readonly proveedorListasCautela: string;
  readonly sagrilaftApiUrl: string;
  readonly tusdatosUrl: string;
  /**
   * Redes desde las que el backend acepta X-Forwarded-For (TRUSTED_PROXY_IPS).
   * Es el CIDR de la VPC: el ALB vive en sus subredes públicas y es lo único
   * que alcanza al backend (Security Group). La aplicación lee aquí la IP real
   * del cliente (backend/api/ip_cliente.py).
   */
  readonly redesProxyConfiables: string;
}

export class ConfigParameters extends Construct {
  public readonly parameterNames: string[];
  public readonly parameterNameByKey: Record<string, string>;
  public readonly parameterByKey: Record<string, ssm.IStringParameter>;

  constructor(scope: Construct, id: string, props: ConfigParametersProps) {
    super(scope, id);

    const prefix = `/sagrilaft/${props.ambiente}`;
    const sagrilaftApiUrl = props.sagrilaftApiUrl || 'dummy://listas-cautela';
    const values: Record<string, string> = {
      APP_ENV: props.ambiente === 'prod' ? 'production' : props.ambiente,
      AWS_REGION: DEFAULT_REGION,
      FRONTEND_URL: `https://${props.dominio},https://${props.dominioPortal}`,
      PORTAL_INTERNO_URL: `https://${props.dominioPortal}`,
      STORAGE_BACKEND: 's3',
      S3_BUCKET: props.s3BucketName,
      BEDROCK_MODEL_ID: props.bedrockModelId,
      BEDROCK_MAX_TOKENS: '4096',
      BEDROCK_TEMPERATURE: '0.0',
      BEDROCK_CONNECT_TIMEOUT_SECONDS: '10',
      BEDROCK_READ_TIMEOUT_SECONDS: '90',
      BEDROCK_MAX_ATTEMPTS: '3',
      BEDROCK_PDF_MAX_PAGES: '7',
      BEDROCK_DEFAULT_CONFIDENCE: '0.90',
      BEDROCK_RESPONSE_LOG_CHARS: '800',
      KEYCLOAK_URL: `http://keycloak.sagrilaft-${props.ambiente}.local:8080`,
      KEYCLOAK_REALM: 'sagrilaft',
      KEYCLOAK_CLIENT_ID: 'sagrilaft-portal',
      KEYCLOAK_ISSUER_URL: `https://${props.dominioKeycloak}`,
      KEYCLOAK_HOSTNAME: props.dominioKeycloak,
      SMTP_HOST: 'email-smtp.us-east-1.amazonaws.com',
      SMTP_PORT: '587',
      SMTP_FROM: props.sesEmailOrigen,
      SMTP_REPLY_TO: props.smtpReplyTo,
      SES_EMAIL_ORIGEN: props.sesEmailOrigen,
      SES_NOTIFICACIONES_ENABLED: 'true',
      ALERTAS_EMAIL_DESTINATARIO: props.alertasEmailDestino,
      SNS_NOTIFICACIONES_ENABLED: 'false',
      ZOHO_REDIRECT_URI: `https://${props.dominioPortal}/oauth/zoho/callback`,
      ZOHO_WEBHOOK_SIGNATURE_HEADER: 'X-ZS-WEBHOOK-SIGNATURE',
      ZOHO_SIGN_TESTING: props.ambiente === 'prod' ? 'false' : 'true',
      ZOHO_REFRESH_MARGIN_SECONDS: '300',
      ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS: '3600',
      ZOHO_HTTP_MAX_ATTEMPTS: '3',
      ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS: '1.0',
      ZOHO_HTTP_BACKOFF_FACTOR: '2',
      ZOHO_TOKEN_TIMEOUT_SECONDS: '15',
      ZOHO_STATUS_TIMEOUT_SECONDS: '15',
      ZOHO_CANCEL_TIMEOUT_SECONDS: '15',
      ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS: '30',
      ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS: '30',
      ZOHO_DOWNLOAD_TIMEOUT_SECONDS: '60',
      ZOHO_SIGN_REQUEST_EXPIRATION_DAYS: '15',
      UVICORN_WORKERS: '4',
      // Antes '172.0.0.0/8': no cubría la VPC (10.0.0.0/16) y el backend veía
      // la IP del ALB como cliente.
      TRUSTED_PROXY_IPS: props.redesProxyConfiables,
      // Staging: dummy (simulado) o sagrilaft (externo, Tusdatos). Produccion: deshabilitado.
      PROVEEDOR_LISTAS_CAUTELA: props.proveedorListasCautela,
      SAGRILAFT_API_URL: sagrilaftApiUrl,
      // Listas v2: custodia de informes y PDF del proveedor en el bucket, bajo su prefijo
      // (ECS no tiene disco persistente), y URL de Tusdatos para la modalidad externa.
      LISTAS_CUSTODIA_BACKEND: 's3',
      LISTAS_CUSTODIA_S3_PREFIJO: 'listas/custodia/',
      LISTAS_TUSDATOS_URL: props.tusdatosUrl,
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
