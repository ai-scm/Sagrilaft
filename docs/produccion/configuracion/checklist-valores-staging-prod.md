# Valores de staging y producción

Función única: catálogo de valores no sensibles y referencia a secretos por ambiente.
Revisión documental: 2026-10-06. Los valores preparados no acreditan su aplicación
en AWS; ver [P03](../PENDIENTES_PRODUCCION.md#p03). Contrato y manejo de secretos:
[Matriz](MATRIZ_AWS_CONFIG.md). Estado del despliegue: [Estado](../../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).

## Criterios Confirmados

- Cuenta AWS objetivo: `<CUENTA_AWS>`.
- Region: `us-east-1`.
- Hosted Zone publica: `ia.blend360.com` (`<HOSTED_ZONE_ID>`).
- Certificado ACM wildcard:
  `<ARN_CERTIFICADO_ACM>`.
- SES sera el canal principal de correos.
- El adaptador SNS del backend queda apagado; las alarmas CloudWatch usan su topic independientemente.
- Zoho Sign queda en sandbox en staging (`ZOHO_SIGN_TESTING=true`) para no
  consumir creditos reales; solo produccion usa firma real.
- Para staging, el despliegue local oficial usa `BEDROCK_MODEL_ID`:
  `amazon.nova-pro-v1:0`.
- `VITE_BACKEND_URL` queda vacio en staging/prod porque el frontend consume `/api`
  relativo y el ALB enruta `/api/*` al backend.
- Cliente Keycloak actual: `sagrilaft-portal`.
- Desarrollo local queda estandarizado con `.env` como archivo fuente para
  Docker Compose.
- **SMTP por ambiente (confirmado 2026-10-20).** Desarrollo local y staging comparten
  la misma credencial SMTP: usuario IAM `sagrilaft-ses-smtppp`, fuente vigente en
  `sagrilaft/staging/smtp_credentials` (Secrets Manager). Producción usa una credencial
  exclusiva y distinta: usuario IAM `ses-smtp-prod-sagrilaft`, fuente vigente en
  `sagrilaft/prod/smtp_credentials`. Ningún ambiente debe generar una credencial SMTP
  nueva para pruebas locales — se reutiliza la de staging. Detalle y pendientes de
  reconciliación: [adenda del checklist de corte](../despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod)
  y [P03](../PENDIENTES_PRODUCCION.md#p03).
- **Zoho Sign por ambiente (reconciliado 2026-10-20).** Staging y producción comparten el
  mismo Self Client de Zoho (mismo `client_id`/`client_secret`/`refresh_token`); solo el
  `webhook_secret` es distinto por ambiente, cada uno con su propio webhook en Zoho Sign
  (`Sagrilaft-Staging` / `Sagrilaft-Produccion`, recreados tras borrarse). `.env.prod` y
  `.env.staging` ya coinciden con sus secretos respectivos; local reutiliza la credencial
  de staging. Detalle: [adenda del checklist de corte](../despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod).

## Staging

### Configuracion SSM

Prefijo esperado: `/sagrilaft/staging/config/`

| Variable | Valor |
|---|---|
| `APP_ENV` | `staging` |
| `AWS_REGION` | `us-east-1` |
| `FRONTEND_URL` | `https://forms-staging-sagrilaft.ia.blend360.com,https://staging-sagrilaft.ia.blend360.com` |
| `PORTAL_INTERNO_URL` | `https://staging-sagrilaft.ia.blend360.com` |
| `STORAGE_BACKEND` | `s3` |
| `S3_BUCKET` | `<BUCKET_S3_STAGING>` |
| `BEDROCK_MODEL_ID` | `amazon.nova-pro-v1:0` |
| `BEDROCK_MAX_TOKENS` | `4096` |
| `BEDROCK_TEMPERATURE` | `0.0` |
| `BEDROCK_CONNECT_TIMEOUT_SECONDS` | `10` |
| `BEDROCK_READ_TIMEOUT_SECONDS` | `90` |
| `BEDROCK_MAX_ATTEMPTS` | `3` |
| `BEDROCK_PDF_MAX_PAGES` | `7` |
| `BEDROCK_DEFAULT_CONFIDENCE` | `0.90` |
| `BEDROCK_RESPONSE_LOG_CHARS` | `800` |
| `PROVEEDOR_LISTAS_CAUTELA` | `deshabilitado` (script vigente; `dummy` es histórico) |
| `SAGRILAFT_API_URL` | no requerida con proveedor deshabilitado; placeholder técnico gestionado por CDK |
| `KEYCLOAK_URL` | `http://keycloak.sagrilaft-staging.local:8080` |
| `KEYCLOAK_REALM` | `sagrilaft` |
| `KEYCLOAK_CLIENT_ID` | `sagrilaft-portal` |
| `KEYCLOAK_ISSUER_URL` | `https://login-staging-sagrilaft.ia.blend360.com` |
| `KEYCLOAK_HOSTNAME` | `login-staging-sagrilaft.ia.blend360.com` |
| `VITE_BACKEND_URL` | vacio |
| `VITE_PORTAL_INTERNO_URL` | `https://staging-sagrilaft.ia.blend360.com` |
| `VITE_KEYCLOAK_URL` | `https://login-staging-sagrilaft.ia.blend360.com` |
| `VITE_KEYCLOAK_REALM` | `sagrilaft` |
| `VITE_KEYCLOAK_CLIENT_ID` | `sagrilaft-portal` |
| `VITE_RAZON_SOCIAL` | `HIGH TECH SOFTWARE S.A.S` |
| `VITE_CORREO_DATOS` | `administrativocol@blend360.com` |
| `SMTP_HOST` | `email-smtp.us-east-1.amazonaws.com` |
| `SMTP_PORT` | `587` |
| `SMTP_FROM` | `no-reply-sagrilaft@ia.blend360.com` (actualizado 2026-09-23, antes `legal@blend360.com`) |
| `SMTP_REPLY_TO` | `legal@blend360.com` |
| `SES_EMAIL_ORIGEN` | `no-reply-sagrilaft@ia.blend360.com` (actualizado 2026-09-23) |
| `SES_NOTIFICACIONES_ENABLED` | `true` |
| `ALERTAS_EMAIL_DESTINATARIO` | `<correo-interno>` |
| `SNS_NOTIFICACIONES_ENABLED` | `false` |
| `ZOHO_REDIRECT_URI` | `https://staging-sagrilaft.ia.blend360.com/oauth/zoho/callback` |
| `ZOHO_WEBHOOK_SIGNATURE_HEADER` | `X-ZS-WEBHOOK-SIGNATURE` |
| `ZOHO_SIGN_TESTING` | `true` |
| `ZOHO_REFRESH_MARGIN_SECONDS` | `300` |
| `ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS` | `3600` |
| `ZOHO_HTTP_MAX_ATTEMPTS` | `3` |
| `ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS` | `1.0` |
| `ZOHO_HTTP_BACKOFF_FACTOR` | `2` |
| `ZOHO_TOKEN_TIMEOUT_SECONDS` | `15` |
| `ZOHO_STATUS_TIMEOUT_SECONDS` | `15` |
| `ZOHO_CANCEL_TIMEOUT_SECONDS` | `15` |
| `ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS` | `30` |
| `ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS` | `30` |
| `ZOHO_DOWNLOAD_TIMEOUT_SECONDS` | `60` |
| `ZOHO_SIGN_REQUEST_EXPIRATION_DAYS` | `15` |
| `UVICORN_WORKERS` | `2` |
| `TRUSTED_PROXY_IPS` | `172.0.0.0/8` |

### Secrets Manager

| Secreto | Campos | Procedencia / referencia |
|---|---|---|
| `sagrilaft/staging/db_credentials` | `username`, `password` | creado por CDK y ya disponible en AWS |
| `sagrilaft/staging/app_secret` | `secret_key` | creado por CDK y ya actualizado en AWS |
| `sagrilaft/staging/zoho_credentials` | `client_id`, `client_secret`, `refresh_token`, `webhook_secret` | cargado con valores reales en AWS |
| `sagrilaft/staging/smtp_credentials` | `username`, `password` | cargado con valores reales en AWS |
| `sagrilaft/staging/keycloak_admin` | `username`, `password` | creado por CDK y ya revisado en AWS |
| `sagrilaft/staging/sagrilaft_listas_cautela_credentials` | `api_key` | no requerido con proveedor deshabilitado; activación en [P15](../PENDIENTES_PRODUCCION.md#p15) |

## Produccion

### Configuracion SSM

Prefijo esperado: `/sagrilaft/prod/config/`

| Variable | Valor |
|---|---|
| `APP_ENV` | `production` |
| `AWS_REGION` | `us-east-1` |
| `FRONTEND_URL` | `https://forms-sagrilaft.ia.blend360.com,https://sagrilaft.ia.blend360.com` |
| `PORTAL_INTERNO_URL` | `https://sagrilaft.ia.blend360.com` |
| `STORAGE_BACKEND` | `s3` |
| `S3_BUCKET` | generado por CDK |
| `BEDROCK_MODEL_ID` | `amazon.nova-pro-v1:0` (valor preparado; ejecución en [P03](../PENDIENTES_PRODUCCION.md#p03)) |
| `BEDROCK_MAX_TOKENS` | `4096` |
| `BEDROCK_TEMPERATURE` | `0.0` |
| `BEDROCK_CONNECT_TIMEOUT_SECONDS` | `10` |
| `BEDROCK_READ_TIMEOUT_SECONDS` | `90` |
| `BEDROCK_MAX_ATTEMPTS` | `3` |
| `BEDROCK_PDF_MAX_PAGES` | `7` |
| `BEDROCK_DEFAULT_CONFIDENCE` | `0.90` |
| `BEDROCK_RESPONSE_LOG_CHARS` | `800` |
| `PROVEEDOR_LISTAS_CAUTELA` | `deshabilitado` (decidido 2026-09-29: aun no hay proveedor de listas de cautela contratado; migrar a `sagrilaft` + `SAGRILAFT_API_URL` real cuando exista) |
| `SAGRILAFT_API_URL` | no aplica mientras `PROVEEDOR_LISTAS_CAUTELA=deshabilitado` |
| `KEYCLOAK_URL` | `http://keycloak.sagrilaft-prod.local:8080` |
| `KEYCLOAK_REALM` | `sagrilaft` |
| `KEYCLOAK_CLIENT_ID` | `sagrilaft-portal` |
| `KEYCLOAK_ISSUER_URL` | `https://login-sagrilaft.ia.blend360.com` |
| `KEYCLOAK_HOSTNAME` | `login-sagrilaft.ia.blend360.com` |
| `VITE_BACKEND_URL` | vacio |
| `VITE_PORTAL_INTERNO_URL` | `https://sagrilaft.ia.blend360.com` |
| `VITE_KEYCLOAK_URL` | `https://login-sagrilaft.ia.blend360.com` |
| `VITE_KEYCLOAK_REALM` | `sagrilaft` |
| `VITE_KEYCLOAK_CLIENT_ID` | `sagrilaft-portal` |
| `VITE_RAZON_SOCIAL` | `HIGH TECH SOFTWARE S.A.S` |
| `VITE_CORREO_DATOS` | `administrativocol@blend360.com` |
| `SMTP_HOST` | `email-smtp.us-east-1.amazonaws.com` |
| `SMTP_PORT` | `587` |
| `SMTP_FROM` | `no-reply-sagrilaft@ia.blend360.com` (actualizado 2026-09-23, antes `legal@blend360.com`) |
| `SMTP_REPLY_TO` | `legal@blend360.com` |
| `SES_EMAIL_ORIGEN` | `no-reply-sagrilaft@ia.blend360.com` (actualizado 2026-09-23) |
| `SES_NOTIFICACIONES_ENABLED` | `true` |
| `ALERTAS_EMAIL_DESTINATARIO` | lista interna Blend confirmada, separada por comas |
| `SNS_NOTIFICACIONES_ENABLED` | `false` |
| `ZOHO_REDIRECT_URI` | `https://sagrilaft.ia.blend360.com/oauth/zoho/callback` |
| `ZOHO_WEBHOOK_SIGNATURE_HEADER` | `X-ZS-WEBHOOK-SIGNATURE` |
| `ZOHO_SIGN_TESTING` | `false` |
| `ZOHO_REFRESH_MARGIN_SECONDS` | `300` |
| `ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS` | `3600` |
| `ZOHO_HTTP_MAX_ATTEMPTS` | `3` |
| `ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS` | `1.0` |
| `ZOHO_HTTP_BACKOFF_FACTOR` | `2` |
| `ZOHO_TOKEN_TIMEOUT_SECONDS` | `15` |
| `ZOHO_STATUS_TIMEOUT_SECONDS` | `15` |
| `ZOHO_CANCEL_TIMEOUT_SECONDS` | `15` |
| `ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS` | `30` |
| `ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS` | `30` |
| `ZOHO_DOWNLOAD_TIMEOUT_SECONDS` | `60` |
| `ZOHO_SIGN_REQUEST_EXPIRATION_DAYS` | `15` |
| `UVICORN_WORKERS` | `4` |
| `TRUSTED_PROXY_IPS` | `172.0.0.0/8` |

### Secrets Manager

| Secreto | Campos | Procedencia / referencia |
|---|---|---|
| `sagrilaft/prod/db_credentials` | `username`, `password` | generado por CDK |
| `sagrilaft/prod/app_secret` | `secret_key` | generado por CDK |
| `sagrilaft/prod/zoho_credentials` | `client_id`, `client_secret`, `refresh_token`, `webhook_secret` | secreto externo a CDK; importar con `zohoSecretYaExiste=true`; [evidencia](../../operacion/RUNBOOK_OPERATIVO.md#zoho), [validación productiva](../PENDIENTES_PRODUCCION.md#p05) |
| `sagrilaft/prod/smtp_credentials` | `username`, `password` | insumo privado local; carga y validación en [P03](../PENDIENTES_PRODUCCION.md#p03) |
| `sagrilaft/prod/keycloak_admin` | `username`, `password` | generado por CDK |
| `sagrilaft/prod/sagrilaft_listas_cautela_credentials` | `api_key` | no requerido mientras `PROVEEDOR_LISTAS_CAUTELA=deshabilitado`; cargar solo cuando exista API real |

<a id="destinatarios"></a>
## Destinatarios de producción

`ALERTAS_EMAIL_DESTINATARIO` acepta varios correos separados por coma. La lista de producción no se publica en el repositorio: se pasa en el contexto de corte como `snsAlertasSub` y queda en SSM. Solicitarla al responsable de cumplimiento.

**Vigente desde la decisión del 2026-10-21:** hasta autorizar a los once destinatarios originales, la lista efectiva es solo `Bryan.Ariza@blend360.com`. La lista completa sigue siendo la prevista, pero no se aplica. Ver [P06](../PENDIENTES_PRODUCCION.md#p06).

## Clientes OAuth Zoho

Data center confirmado: USA (`accounts.zoho.com`, `sign.zoho.com`,
`api-console.zoho.com`).

Scopes recomendados para el flujo actual:

- `ZohoSign.documents.ALL`

El backend crea solicitudes, consulta estado, cancela y descarga PDFs firmados.
No usa templates hoy; `ZohoSign.templates.ALL` solo seria necesario si luego
migramos a flujos basados en templates de Zoho.

Staging:

- Client name: `Sagrilaft_Staging`
- Homepage URL: `https://staging-sagrilaft.ia.blend360.com`
- Authorized Redirect URI:
  `https://staging-sagrilaft.ia.blend360.com/oauth/zoho/callback`

Produccion:

- Client name: `Sagrilaft_Produccion`
- Homepage URL: `https://sagrilaft.ia.blend360.com`
- Authorized Redirect URI:
  `https://sagrilaft.ia.blend360.com/oauth/zoho/callback`

El Redirect URI se usa para obtener el `authorization_code` y luego generar el
`refresh_token`. Tambien se envia al refrescar access tokens, segun la
documentacion de Zoho. No es el link de firma que recibe la contraparte.

Webhooks esperados de Zoho Sign:

- Staging: `https://forms-staging-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign`
- Produccion: `https://forms-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign`

Configuracion recomendada del webhook en Zoho:

- Nombre produccion: `Sagrilaft-Produccion`.
- URL de respuesta produccion:
  `https://forms-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign`.
- Nombre staging: `Sagrilaft-Staging`.
- URL de respuesta staging:
  `https://forms-staging-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign`.
- Eventos a marcar:
  - `Completados por todos`;
  - `Expira`;
  - `Retirado`;
  - `Rechazado`;
  - `Duro rebotado`.
- Eventos a dejar apagados por ahora:
  - `Enviados`;
  - `Viendo`;
  - `Firmados por un destinatario`;
  - `Aprobados por un destinatario`;
  - `Reasignados`.
- Seguridad:
  - habilitar firma HMAC SHA-256;
  - clave secreta: mismo valor privado que `ZOHO_WEBHOOK_SECRET`;
  - algoritmo: `SHA-256`;
  - cabecera de firma: `X-ZS-WEBHOOK-SIGNATURE`;
  - no habilitar Basic Auth ni mTLS por ahora.

La URL de respuesta usa el dominio `forms-*` porque ese hostname es publico y el
ALB enruta `/api/*` al backend ECS antes de entregar trafico al frontend. El
webhook lo procesa el backend, no el frontend del formulario.
