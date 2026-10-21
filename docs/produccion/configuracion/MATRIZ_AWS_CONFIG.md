# Matriz AWS Config

Función única: contrato de configuración (nombre, origen, destino y consumo).
Los valores por ambiente están en el [catálogo](checklist-valores-staging-prod.md),
y su verificación se gestiona en [P03](../PENDIENTES_PRODUCCION.md#p03).

## Credenciales AWS por ambiente (no secretos de aplicación)

**Actualizado 2026-10-20.** `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` **no existen**
en ningún ambiente, ni siquiera en `.env` local — no son parte de esta matriz de
secretos de aplicación porque no viven en Secrets Manager en ningún caso:

- **Staging/producción (ECS):** credenciales temporales del Task Role (`backendTaskRole`
  en `infra/sagrilaft/lib/constructs/ecs-fargate.ts`). Sin cambios.
- **Local:** sesión SSO del desarrollador (`aws sso login --profile <perfil>`), definida
  en `AWS_PROFILE` (`.env`) y montada en el contenedor por `docker-compose.dev.yml`
  (`~/.aws/config` y `~/.aws/sso`, de solo lectura; `~/.aws/credentials` nunca se monta).
  Antes, local usaba claves estáticas en `.env` — se eliminaron por buenas prácticas
  (sin credenciales de larga duración en archivos) y porque la clave que había ya no
  era válida en AWS.
- **`BEDROCK_MODEL_ID` en local:** debe apuntar a una cuenta donde el perfil SSO usado
  tenga acceso real a Bedrock. Verificado el 2026-10-20 con el perfil
  `PS-PowerUserAccess-<CUENTA_AWS>`: `claude-sonnet-4-6` falla con
  `AccessDeniedException` (permisos de AWS Marketplace); `us.amazon.nova-pro-v1:0` sí
  funciona (invocación real probada) y además coincide con el valor ya documentado para
  staging/producción en el [catálogo](checklist-valores-staging-prod.md).
- **Decisión 2026-10-20:** staging y producción usan `amazon.nova-pro-v1:0`. Claude Sonnet
  4.6 tiene mayor precisión al extraer datos de documentos.
- **Staging ya corre con `amazon.nova-pro-v1:0` (verificado en SSM).** No fue un cambio
  deliberado y aislado: ocurrió como efecto colateral del `cdk deploy` que activó el NAT
  Gateway ese mismo día — el script `deploy:staging` de `infra/sagrilaft/package.json`
  trae `-c bedrockModelId=${BEDROCK_MODEL_ID:-amazon.nova-pro-v1:0}`, y como no se exportó
  `BEDROCK_MODEL_ID` en esa sesión, tomó el valor por defecto. Antes, staging corría
  `claude-sonnet-4-6` en vivo (ver discrepancia documentada en
  [VARIABLES_DE_ENTORNO.md](VARIABLES_DE_ENTORNO.md)). `.env.staging` ya se corrigió para
  reflejar el valor real.
- **Producción ya tenía `amazon.nova-pro-v1:0` en SSM desde el bootstrap del 2026-10-07**
  (el comando de bootstrap en `CHECKLIST_CORTE_PRODUCCION.md` ya pasaba ese valor por
  contexto); no es un cambio de esta sesión. Es irrelevante en la práctica porque
  producción sigue con `desiredCount=0` — ningún contenedor lo está usando todavía.

### Procedimiento: sesión SSO para desarrollo local

1. `aws sso login --profile PS-PowerUserAccess-<CUENTA_AWS>` (o el perfil que te hayan
   asignado). Abre el navegador para autenticar.
2. En `.env`, define `AWS_PROFILE=<ese perfil>`.
3. Levanta el backend normalmente: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate backend`.
4. Verificar que tomó la sesión: `docker exec solucion-backend-1 python3 -c "import boto3; print(boto3.Session().get_credentials().method)"` debe imprimir `sso`.
5. La sesión SSO expira sola (unas horas); cuando expire, repetir el paso 1 y recrear el
   backend.

## Secrets Manager

Estos valores son sensibles y no deben quedar como runtime final en archivos
locales cuando staging/prod ya existan en AWS.

Regla de escritura: CDK crea todos los secretos. Son **externos** (CDK los crea
vacíos o los importa, y se cargan con `sync_aws_runtime_assets.py --apply`):
`zoho_credentials`, `smtp_credentials` y `sagrilaft_listas_cautela_credentials`.
Son **administrados por CDK** y nunca se escriben desde `.env*`: `app_secret`,
`db_credentials`, `keycloak_admin`.

### `sagrilaft/{env}/app_secret`

- `secret_key`

Origen: generado por CDK en Secrets Manager. ECS consume este secreto.
Es administrado por CDK: `sync_aws_runtime_assets.py` **no lo escribe**. El
La clave `SECRET_KEY` se eliminó de `.env.prod` el 2026-10-19: ningún script local la lee y el valor de ECS es el generado.
Última escritura esperada: 2026-10-07 08:00:34 (-05:00), creación por CloudFormation.

### `sagrilaft/{env}/zoho_credentials`

- `client_id`
- `client_secret`
- `refresh_token`
- `webhook_secret`

Fuente vigente en AWS: carga manual (cuenta oficial de Legal), última escritura el
2026-09-24 a las 13:03 (-05:00). Confirmada como fuente final el 2026-10-20: el
`client_id`/`client_secret` coinciden con el único Self Client de la cuenta Zoho revisada
en API Console ([P03](../PENDIENTES_PRODUCCION.md#p03)).

Nota (2026-10-20): `staging` y `prod` comparten el mismo `client_id`/`client_secret`/
`refresh_token` en AWS — un solo Self Client sirve a ambos ambientes. Solo
`webhook_secret` es distinto entre los dos secretos (cada ambiente tiene su propio
webhook en Zoho Sign). Esto difiere de la intención original documentada en el
[catálogo](checklist-valores-staging-prod.md#clientes-oauth-zoho) de tener dos clientes
OAuth separados (`Sagrilaft_Staging`/`Sagrilaft_Produccion`); no se corrigió porque
funciona así desde la migración de cuenta y no bloquea nada.

Origen en archivos locales:

- `.env.staging` -> `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`,
  `ZOHO_WEBHOOK_SECRET`. Reconciliado con `sagrilaft/staging/zoho_credentials` el 2026-10-20.
- `.env.prod` -> mismos campos. Reconciliado con `sagrilaft/prod/zoho_credentials` el
  2026-10-20.
- `.env` (local) -> mismos campos, con el valor de `sagrilaft/staging/zoho_credentials`
  (local reutiliza la credencial de staging, igual que SMTP). `ZOHO_REDIRECT_URI` de local
  sigue siendo distinto (`localhost`) porque Zoho no puede llamar a un webhook local.

### `sagrilaft/{env}/smtp_credentials`

- `username`
- `password`

Fuente vigente en AWS: `sagrilaft-ses-smtppp` (staging) y `ses-smtp-prod-sagrilaft`
(producción), reconciliadas con `.env.staging`/`.env.prod` el 2026-10-20
([P03](../PENDIENTES_PRODUCCION.md#p03)).

**Adenda 2026-10-20 — separación confirmada por ambiente.** `sagrilaft/staging/smtp_credentials`
corresponde al usuario IAM `sagrilaft-ses-smtppp` (no `sagrilaft-ses-smtpp` como se había
identificado el 2026-10-16); probado end-to-end (login + envío real). Esta misma credencial
se reutiliza en desarrollo local. `sagrilaft/prod/smtp_credentials` corresponde a un usuario
IAM distinto, `ses-smtp-prod-sagrilaft`, exclusivo de producción; también probado
exitosamente y ya reconciliado con `.env.prod`. `sagrilaft-ses-smtpp` (doble "p") no está en
uso confirmado por ningún ambiente.

Origen en archivos locales (no es fuente vigente hasta conciliarlo):

- `.env` (desarrollo local) -> `SMTP_USER`, `SMTP_PASSWORD`. Debe reutilizar el valor de
  `sagrilaft/staging/smtp_credentials`, no una credencial propia.
- `.env.staging` -> `SMTP_USER`, `SMTP_PASSWORD`. Debe coincidir con
  `sagrilaft/staging/smtp_credentials` (usuario `sagrilaft-ses-smtppp`).
- `.env.prod` -> `SMTP_USER`, `SMTP_PASSWORD`. Reconciliado el 2026-10-20 contra
  `ses-smtp-prod-sagrilaft`, la identidad real de producción.

### `sagrilaft/{env}/keycloak_admin`

- `username`
- `password`

Estado esperado:

- `username=admin`
- `password` generado por CDK (32 caracteres).
- Última escritura esperada: 2026-10-07 08:00:35 (-05:00), creación por CloudFormation.

Nota:

- Administrado por CDK. `sync_aws_runtime_assets.py` **no lo escribe**: reemplazar
  la contraseña desde `.env.*` desincroniza la de Keycloak.
- `KEYCLOAK_ADMIN_PASSWORD` de `.env.staging` no es el valor de runtime. En `.env.prod` se eliminó el 2026-10-19 (sin consumidor local); la fuente vigente es el secreto `keycloak_admin`.

### `sagrilaft/{env}/db_credentials`

- `username`
- `password`

Estado esperado:

- generado por CDK (contraseña de 32 caracteres). RDS la usa como credencial
  (`rds.Credentials.fromSecret`) y ECS la inyecta en `DB_USER`/`DB_PASSWORD`.
- Última escritura esperada: 2026-10-07 08:13:19 (-05:00), asociación con RDS por
  `SecretTargetAttachment` de CloudFormation.

Nota:

- Administrado por CDK. `sync_aws_runtime_assets.py` **no lo escribe**. Cambiar el
  valor del secreto no cambia la contraseña de RDS: las tareas nuevas dejarían de conectar.
- Si Keycloak usa credenciales separadas sobre RDS, ese dato debe quedar
  documentado aparte o resolverse con el usuario final definido para Keycloak.

### `sagrilaft/{env}/sagrilaft_listas_cautela_credentials`

- `api_key`

Origen actual:

- `.env.staging` -> `SAGRILAFT_API_KEY`
- `.env.prod` -> `SAGRILAFT_API_KEY`

Nota:

- el valor final en ECS debe venir desde Secrets Manager. No debe quedar como
  variable no sensible en SSM.
- Solo se escribe si `PROVEEDOR_LISTAS_CAUTELA=sagrilaft` y `SAGRILAFT_API_KEY` tiene
  un valor real (no vacío ni `REPLACE_*`). Con `deshabilitado` el script lo omite.
  Requiere que CDK haya creado el secreto antes. Procedimiento:
  [secretos externos](../despliegue/CHECKLIST_CORTE_PRODUCCION.md#secretos-externos).

## SSM Parameter Store

Estos valores son configuracion no sensible de runtime.

Prefijo:

- staging: `/sagrilaft/staging/config/`
- prod: `/sagrilaft/prod/config/`

### Backend / runtime general

- `APP_ENV`
- `AWS_REGION`
- `FRONTEND_URL`
- `PORTAL_INTERNO_URL`
- `UVICORN_WORKERS`
- `TRUSTED_PROXY_IPS`
- `STORAGE_BACKEND`
- `S3_BUCKET`
- `BEDROCK_MODEL_ID`
- `BEDROCK_MAX_TOKENS`
- `BEDROCK_TEMPERATURE`
- `BEDROCK_CONNECT_TIMEOUT_SECONDS`
- `BEDROCK_READ_TIMEOUT_SECONDS`
- `BEDROCK_MAX_ATTEMPTS`
- `BEDROCK_PDF_MAX_PAGES`
- `BEDROCK_DEFAULT_CONFIDENCE`
- `BEDROCK_RESPONSE_LOG_CHARS`

### Listas de cautela / proveedor SAGRILAFT

- `PROVEEDOR_LISTAS_CAUTELA`
- `SAGRILAFT_API_URL`

### Zoho

- `ZOHO_REDIRECT_URI`
- `ZOHO_WEBHOOK_SIGNATURE_HEADER`
- `ZOHO_SIGN_TESTING`
- `ZOHO_REFRESH_MARGIN_SECONDS`
- `ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS`
- `ZOHO_HTTP_MAX_ATTEMPTS`
- `ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS`
- `ZOHO_HTTP_BACKOFF_FACTOR`
- `ZOHO_TOKEN_TIMEOUT_SECONDS`
- `ZOHO_STATUS_TIMEOUT_SECONDS`
- `ZOHO_CANCEL_TIMEOUT_SECONDS`
- `ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS`
- `ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS`
- `ZOHO_DOWNLOAD_TIMEOUT_SECONDS`
- `ZOHO_SIGN_REQUEST_EXPIRATION_DAYS`

### Correo / notificaciones

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM`
- `SMTP_REPLY_TO`
- `SES_EMAIL_ORIGEN`
- `SES_NOTIFICACIONES_ENABLED`
- `ALERTAS_EMAIL_DESTINATARIO`
- `SNS_NOTIFICACIONES_ENABLED`

### Keycloak

- `KEYCLOAK_HOSTNAME`
- `KEYCLOAK_URL`
- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_ISSUER_URL`

### Frontend build-time que hoy viven en `.env.staging` y `.env.prod`

Estos no son secretos, pero tampoco se consumen como runtime del backend. Se usan
al construir las imagenes de frontend antes de subirlas a ECR.

- `VITE_BACKEND_URL`
- `VITE_PORTAL_INTERNO_URL`
- `VITE_KEYCLOAK_URL`
- `VITE_KEYCLOAK_REALM`
- `VITE_KEYCLOAK_CLIENT_ID`
- `VITE_RAZON_SOCIAL`
- `VITE_CORREO_DATOS`

## No Debe Ir A AWS Runtime

Estos valores pueden existir en `.env` local, pero no deben quedar como runtime
final de staging/prod en ECS.

- `DATABASE_URL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `PORT_PUBLICO`
- `PORT_PORTAL`
- `PORTAL_AUTH_DISABLED`
- `KEYCLOAK_DB_URL`

## Inyección de destinatarios CDK

`snsAlertasSub` determina las suscripciones SNS y `ALERTAS_EMAIL_DESTINATARIO`
en SSM. CDK no lee ese dato de `.env.prod` automáticamente. La lista se mantiene
en el [catálogo](checklist-valores-staging-prod.md#destinatarios); los comandos
la pasan mediante el [contexto común](../despliegue/CHECKLIST_CORTE_PRODUCCION.md#contexto).
`SNS_NOTIFICACIONES_ENABLED=false` desactiva el adaptador de alertas del backend,
no las alarmas CloudWatch conectadas directamente al topic.

## Insumos privados

Los `.env.*` privados sirven como insumo local; no son runtime AWS. Los secretos
se cargan en Secrets Manager y nunca se copian en documentación. Las plantillas
`.env.*.example` solo declaran nombres. El inventario seguro puede realizarse
con [audit_aws_secrets_safe.py](../../../scripts/aws/audit_aws_secrets_safe.py).
