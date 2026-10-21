# Variables de entorno (`.env*`)

Función única: referencia por variable de los archivos `.env`, `.env.dev.example`,
`.env.staging(.example)` y `.env.prod(.example)`: significado, consumo, origen,
diferencias por ambiente, obligatoriedad y sensibilidad.

Elaborado el 2026-10-16 a partir del código (`backend/infrastructure/config/configuracion.py`,
`backend/entrypoint.sh`, `docker-compose*.yml`, `infra/sagrilaft/lib/**`, `scripts/**`,
`frontend/**`). **No contiene valores secretos** (ni contraseñas, tokens, claves, IDs de
cliente OAuth ni IDs de acceso AWS). Los valores concretos no sensibles por ambiente
siguen en [Valores por ambiente](checklist-valores-staging-prod.md) y el contrato de
Secrets Manager/SSM en la [Matriz AWS](MATRIZ_AWS_CONFIG.md).

Todo lo que aquí se afirma sale del código; lo que no pudo comprobarse se marca como
**(no verificado)**.

## 1. Cómo se usa cada archivo (léase antes)

| Archivo | Ambiente | ¿Qué hace realmente? | En Git |
|---|---|---|---|
| `.env` | Desarrollo local | Lo lee Docker Compose (sustitución `${VAR}` en `docker-compose.yml` + `docker-compose.dev.yml`). Es el único archivo que alimenta un runtime directamente. | Ignorado (`.gitignore:2`) |
| `.env.dev.example` | Desarrollo | Plantilla de referencia. **Confirmado 2026-10-20: no es necesario copiarla a `.env` en el día a día** — `.env` ya existe, está poblado y es la fuente que usa Docker Compose. Solo sirve para armar un `.env` desde cero (onboarding) o para ver qué variable existe y su comentario. | Versionado |
| `.env.staging` / `.env.prod` | Staging / producción | **No son runtime.** Los consumen solo scripts de despliegue: `scripts/despliegue/build_and_push_ecr_images.py` (args de build `VITE_*`, `AWS_REGION`, `KEYCLOAK_*_URL`) y `scripts/aws/sync_aws_runtime_assets.py` (escribe en Secrets Manager solo las credenciales externas a CDK: Zoho, SMTP y, si aplica, la API de listas; nunca `app_secret`, `db_credentials` ni `keycloak_admin`). | Ignorados (`.gitignore:3`, patrón `.env.*`) |
| `.env.staging.example` / `.env.prod.example` | Staging / producción | Plantillas con marcadores `REPLACE_STAGING_*` / `REPLACE_PROD_*`. | Versionados |

En AWS (ECS Fargate) el backend recibe su configuración de:

- **SSM Parameter Store** `/sagrilaft/{env}/config/*`: lo crea CDK en
  `infra/sagrilaft/lib/constructs/config-parameters.ts`, con valores derivados de
  `-c` (contexto CDK) y constantes del código, **no** de `.env.staging`/`.env.prod`.
- **Secrets Manager** `sagrilaft/{env}/*`: secretos (ver §3 a §7).
- **Valores fijos de CDK** en `ecs-fargate.ts` (`UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`,
  `SNS_TOPIC_ARN`, `KEYCLOAK_DB_URL`, …).

Consecuencia práctica: cambiar `UVICORN_WORKERS`, `TRUSTED_PROXY_IPS`, `SMTP_FROM`,
etc. en `.env.prod` **no cambia nada en AWS**; esos valores solo documentan la intención.
Para cambiarlos hay que modificar el contexto/código CDK y redesplegar.

Validadores existentes: `python3 scripts/validacion/validate_envs.py` (solo comprueba
presencia de claves en los `.example`, no valores) y `check_staging_readiness.py`
(`phase0-env-contract`).

Leyenda de las tablas: **Obl.** = obligatoria (el backend/compose falla sin ella);
**Opc.** = opcional con default; **Sens.** = sensible (🔒 secreto; ⚠️ semi-sensible/dato
personal o de infraestructura; — no sensible).

## 2. Núcleo y entorno

| Variable | Qué es / para qué sirve | Dónde se usa | Origen del valor | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `APP_ENV` | Entorno: `development`, `staging` o `production`. Activa guardrails (S3 obligatorio, `dummy` prohibido en prod, bloqueo de `PORTAL_AUTH_DISABLED`). | `configuracion.py:entorno_actual()`, `autenticacion.py`, `sns_health.py`, `entrypoint.sh`, compose | Dev: `.env`. AWS: SSM (CDK: `prod`→`production`) | **Obl. en backend** (sin default; falla al arrancar). `entrypoint.sh` asume `development` y compose base `production` si falta | — |
| `AWS_REGION` | Región AWS para Bedrock, S3 y SES. | `AWSConfig`, `S3Config`, scripts de despliegue, CI | Dev: `.env`. AWS: constante CDK (`us-east-1`) | Opc. (default `us-east-1`) | — |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | **Eliminadas en los tres ambientes (2026-10-20).** Ya no existen en `.env`, `docker-compose.yml` ni en staging/prod. | — | — | Prohibidas en los tres ambientes (`validate_envs.py`, `check_staging_readiness.py`) | — |
| `AWS_PROFILE` | Perfil de AWS CLI/SSO que usa el backend en local. Reemplaza las claves estáticas. | `boto3` (cadena de credenciales por defecto) | Dev: `.env` (`PS-PowerUserAccess-<CUENTA_AWS>` al 2026-10-20). AWS: no aplica (Task Role) | Opc. en dev (default `default`, sin credenciales → IA deshabilitada). No existe en staging/prod | ⚠️ (nombre de perfil con ID de cuenta) |
| `UVICORN_WORKERS` | Número de procesos Uvicorn. | `backend/entrypoint.sh` (`--workers`) | Dev: compose lo fija en `1` (`docker-compose.dev.yml:100`). AWS: CDK fija `4` | Opc. (default 4) | — |
| `TRUSTED_PROXY_IPS` | IPs/CIDR de proxies de confianza para `X-Forwarded-*`. | `entrypoint.sh` (`--forwarded-allow-ips`) | Dev: compose fija `172.0.0.0/8`. AWS: CDK fija `172.0.0.0/8` | Opc. (default del script `127.0.0.1`; compose base `172.0.0.0/8`) | ⚠️ |
| `SECRET_KEY` | Clave HMAC-SHA256 para firmar reportes de auditoría. | `AppConfig.secret_key` (`os.environ["SECRET_KEY"]`); compose base la exige | Dev: `.env`. `.env.prod`: eliminada el 2026-10-19 (sin consumidor local). AWS: secreto `app_secret.secret_key` (CDK lo genera de 64 caracteres) | **Obl.** (sin default; `KeyError` si falta) | 🔒 |
| `MAX_UPLOAD_SIZE_MB` | Tope de tamaño de archivos subidos. | `AppConfig.max_upload_mb` | AWS: CDK fija `15` en `ecs-fargate.ts`. Dev: **no se inyecta** (ver §9.1, hallazgo 7) | Opc. (default 15) | — |
| `JWKS_CACHE_TTL_SECONDS` | Segundos de caché de las claves JWKS de Keycloak. | `api/middleware/autenticacion.py:84` | Solo documentada en `.env.dev.example` (vacía) y **no inyectada por compose ni CDK** | Opc. (default 300). Vacía rompe el arranque (ver §9.1, hallazgo 6) | — |
| `PORTAL_AUTH_DISABLED` | `true` desactiva la autenticación del portal interno (solo desarrollo). | `autenticacion.py` (aborta si es `true` fuera de `development/local/test`) | Dev: compose (`${PORTAL_AUTH_DISABLED:-true}`). AWS: no se define | Opc. (sin definir ⇒ autenticación activa) | — (riesgo de seguridad si es `true`) |

## 3. Base de datos y puertos (solo desarrollo)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `DATABASE_URL` | URL SQLAlchemy de PostgreSQL. | `configuracion.py:_require_db_url`, `entrypoint.sh`, `alembic/env.py` | Dev: compose dev la **reconstruye** con `POSTGRES_*` y el host `postgres` (el valor del `.env` se ignora). AWS: el `command` ECS la compone con el secreto `db_credentials` y el host RDS (`ecs-fargate.ts`) | **Obl.** | 🔒 (lleva contraseña) |
| `POSTGRES_DB` | Nombre de la BD del contenedor Postgres. | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | — |
| `POSTGRES_USER` | Usuario de Postgres (también usado por Keycloak en dev). | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | ⚠️ |
| `POSTGRES_PASSWORD` | Contraseña de Postgres (también Keycloak en dev). | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | 🔒 |
| `PORT_PUBLICO` | Puerto host del formulario público. | `docker-compose.yml:207` (`${PORT_PUBLICO:-80}:8080`) | `.env` | Opc. (default 80) | — |
| `PORT_PORTAL` | Puerto host del portal interno. | `docker-compose.yml:235` (default 81) | `.env` | Opc. (default 81) | — |

## 4. Frontend y CORS

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `FRONTEND_URL` | Orígenes CORS permitidos (lista separada por comas). También su primer elemento alimenta `KEYCLOAK_FORMULARIO_URL` en el build de Keycloak. | `AppConfig.frontend_urls`, `build_and_push_ecr_images.py:130` | Dev: `.env`. AWS: SSM (`https://{dominio},https://{dominioPortal}`) | **Obl. en staging/prod** (`load_config` falla); en dev default `http://localhost:5173`. Compose base la exige | — |
| `PORTAL_INTERNO_URL` | URL base del portal; se usa en enlaces de correos de alerta. | `AppConfig.portal_interno_url` | Dev: `.env`. AWS: SSM (`https://{dominioPortal}`) | **Obl.** (sin default) | — |
| `VITE_BACKEND_URL` | Origen del backend para el frontend. **Vacío = mismo origen (`/api` relativo)**, lo que usan staging/prod. En dev es el *target* del proxy de Vite. | `vite.config.js` (ambas apps), Dockerfiles (build arg), `build_and_push_ecr_images.py` (la clave debe existir; vacío permitido) | Dev: `.env`. Build AWS: `.env.staging`/`.env.prod` | Obl. como clave en el build; valor vacío válido | — |
| `VITE_PORTAL_INTERNO_URL` | URL del portal embebida en el build del formulario público (enlaces cruzados) y fallback en Keycloak. | `formulario-publico/src/App.jsx`, Dockerfile, build script, CI | `.env*` / CI (`vars.*`) | **Obl.** en el build script | — |
| `VITE_KEYCLOAK_URL` | URL pública de Keycloak para el login del portal. Vacía en dev ⇒ el frontend no redirige al login. | `portal-interno/src/keycloak.js`, `main.jsx` | ídem | **Obl.** en build staging/prod | — |
| `VITE_KEYCLOAK_REALM` | Realm Keycloak del portal. | `keycloak.js` | ídem | Opc. (default `sagrilaft`) | — |
| `VITE_KEYCLOAK_CLIENT_ID` | Client ID Keycloak del portal. | `keycloak.js` | ídem | Opc. (default `sagrilaft-portal`) | — |
| `VITE_RAZON_SOCIAL` | Razón social en textos legales (Habeas Data). | `formulario-publico/src/config/textos-legales.js`, build script y **backend** `services/formulario/exportacion_pdf.py:35` | Build: `.env*`. Backend: ver §9.1, hallazgo 8 | Opc. (defaults en código) | — |
| `VITE_CORREO_DATOS` | Correo para ejercer derechos de Habeas Data. | `textos-legales.js`, `exportacion_pdf.py:36` | ídem | Opc. (default en código) | ⚠️ (correo corporativo) |

Las variables `VITE_*` se **incrustan en el bundle en el build**: son públicas por
definición; nunca deben contener secretos.

## 5. Integraciones: Bedrock, Zoho Sign, correo, listas, SNS

### 5.1 Bedrock (IA de extracción)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `BEDROCK_MODEL_ID` | Modelo o *inference profile* de Bedrock. Vacío ⇒ IA deshabilitada (solo `warning`). | `AWSConfig.model_id` | Dev: `.env`. AWS: contexto CDK `-c bedrockModelId` (default `DEFAULT_BEDROCK_MODEL_ID`) | Opc. en dev; **Obl. en staging/prod** (CDK aborta si va vacío) | ⚠️ (el ARN contiene ID de cuenta AWS) |
| `BEDROCK_MAX_TOKENS` | Tokens máximos de respuesta. | `AWSConfig.max_tokens` | CDK fija `4096` | Opc. (4096) | — |
| `BEDROCK_TEMPERATURE` | Temperatura del modelo. | `AWSConfig.temperature` | CDK `0.0` | Opc. (0.0) | — |
| `BEDROCK_CONNECT_TIMEOUT_SECONDS` | Timeout de conexión. | `AWSConfig` | CDK `10` | Opc. (10) | — |
| `BEDROCK_READ_TIMEOUT_SECONDS` | Timeout de lectura. | `AWSConfig` | CDK `90` | Opc. (90) | — |
| `BEDROCK_MAX_ATTEMPTS` | Reintentos máximos. | `AWSConfig` | CDK `3` | Opc. (3) | — |
| `BEDROCK_PDF_MAX_PAGES` | Páginas máximas de PDF enviadas al modelo. | `AWSConfig` | CDK `7` | Opc. (7) | — |
| `BEDROCK_DEFAULT_CONFIDENCE` | Confianza asignada por defecto a los campos extraídos. | `AWSConfig` | CDK `0.90` | Opc. (0.90) | — |
| `BEDROCK_RESPONSE_LOG_CHARS` | Caracteres de la respuesta del modelo que se registran en log. | `AWSConfig` | CDK `800` | Opc. (800) | — |

### 5.2 Zoho Sign (firma electrónica)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `ZOHO_CLIENT_ID` | Client ID OAuth de Zoho. | `ZohoSignConfig.validar()` | Zoho API Console. AWS: secreto `zoho_credentials.client_id` (subido con `sync_aws_runtime_assets.py`) | **Obl.** (falla `validar()`) | 🔒 (tratar como credencial) |
| `ZOHO_CLIENT_SECRET` | Secret OAuth. | ídem | secreto `zoho_credentials.client_secret` | **Obl.** | 🔒 |
| `ZOHO_REFRESH_TOKEN` | Refresh token OAuth. | ídem | secreto `zoho_credentials.refresh_token` | **Obl.** | 🔒 |
| `ZOHO_REDIRECT_URI` | URI de callback OAuth registrada en Zoho. | `ZohoSignConfig` | Dev: `.env`. AWS: SSM (`https://{dominioPortal}/oauth/zoho/callback`) | **Obl.** (falla `validar()`) | — |
| `ZOHO_WEBHOOK_SECRET` | Secreto HMAC del webhook de Zoho. | `FirmaService` (valida firma del webhook), `routers/webhooks.py` | secreto `zoho_credentials.webhook_secret` | Opc. al arrancar; el webhook falla con `RuntimeError` si falta | 🔒 |
| `ZOHO_WEBHOOK_SIGNATURE_HEADER` | Nombre del header con la firma. | `ZohoSignConfig` | CDK `X-ZS-WEBHOOK-SIGNATURE` | Opc. (ese valor) | — |
| `ZOHO_SIGN_TESTING` | `true` = modo sandbox de Zoho (no consume créditos). | `ZohoSignConfig.modo_prueba` | CDK: `false` solo en `prod`; `true` en el resto. Dev: compose default `true` | Opc. (default código `false`) | — |
| `ZOHO_REFRESH_MARGIN_SECONDS` | Margen de renovación anticipada del access token. | `ZohoSignConfig` | CDK `300` | Opc. (300) | — |
| `ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS` | Vigencia asumida del token si Zoho no la informa. | ídem | CDK `3600` | Opc. (3600) | — |
| `ZOHO_HTTP_MAX_ATTEMPTS` | Reintentos HTTP. | ídem | CDK `3` | Opc. (3) | — |
| `ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS` | Espera inicial entre reintentos. | ídem | CDK `1.0` | Opc. (1.0) | — |
| `ZOHO_HTTP_BACKOFF_FACTOR` | Factor de backoff exponencial. | ídem | CDK `2` | Opc. (2) | — |
| `ZOHO_TOKEN_TIMEOUT_SECONDS` | Timeout del endpoint de token. | ídem | CDK `15` | Opc. (15) | — |
| `ZOHO_STATUS_TIMEOUT_SECONDS` | Timeout de consulta de estado. | ídem | CDK `15` | Opc. (15) | — |
| `ZOHO_CANCEL_TIMEOUT_SECONDS` | Timeout de cancelación. | ídem | CDK `15` | Opc. (15) | — |
| `ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS` | Timeout al crear solicitud. | ídem | CDK `30` | Opc. (30) | — |
| `ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS` | Timeout al enviar solicitud. | ídem | CDK `30` | Opc. (30) | — |
| `ZOHO_DOWNLOAD_TIMEOUT_SECONDS` | Timeout de descarga de documentos. | ídem | CDK `60` | Opc. (60) | — |
| `ZOHO_SIGN_REQUEST_EXPIRATION_DAYS` | Días de vigencia de una solicitud de firma. | ídem | CDK `15` | Opc. (15) | — |

### 5.3 Correo (SMTP/SES) y alertas

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `SMTP_HOST` | Servidor SMTP (endpoint SES `email-smtp.us-east-1.amazonaws.com`). | `SmtpConfig` | CDK constante | Opc. (vacío ⇒ sin SMTP) | — |
| `SMTP_PORT` | Puerto (587, STARTTLS). | `SmtpConfig` | CDK `587` | Opc. (587) | — |
| `SMTP_USER` | Usuario SMTP de SES. | `SmtpConfig`; `sync_aws_runtime_assets.py` | AWS: secreto `smtp_credentials.username` | Opc. en código; **Obl. para el sync** | 🔒 |
| `SMTP_PASSWORD` | Contraseña SMTP de SES. | ídem | secreto `smtp_credentials.password` | ídem | 🔒 |
| `SMTP_FROM` | Remitente visible para contrapartes. | `SmtpConfig.remitente` | AWS: SSM (= `sesEmailOrigen`, contexto CDK) | Opc. (vacío) | ⚠️ |
| `SMTP_REPLY_TO` | Dirección de respuesta. | `SmtpConfig.responder_a` | AWS: SSM (contexto `smtpReplyTo`) | Opc. (vacío). **No la inyecta compose** (§9.1, hallazgo 7) | ⚠️ |
| `SES_EMAIL_ORIGEN` | Remitente verificado en SES para alertas internas HTML. | `SesConfig` | AWS: SSM | Opc.; `configurado` exige también `SES_NOTIFICACIONES_ENABLED=true` | ⚠️ |
| `SES_NOTIFICACIONES_ENABLED` | Interruptor de alertas por SES. | `SesConfig.habilitado` | CDK `true`. Compose default `false` | Opc. (`false`) | — |
| `ALERTAS_EMAIL_DESTINATARIO` | Destinatario(s) internos de alertas (lista separada por comas). | `infrastructure/notificaciones/ses_alertas.py:137` | AWS: SSM (contexto `snsAlertasSub`) | Opc.; si está vacía no se envía ("sin destinatarios") | ⚠️ (datos personales) |
| `SNS_NOTIFICACIONES_ENABLED` | Interruptor del adaptador SNS (hoy apagado; SES es el canal). | `SnsConfig.habilitado` | CDK `false` | Opc. (`false`) | — |
| `SNS_TOPIC_ARN` | ARN del topic SNS de alertas. | `SnsConfig.topic_arn` | AWS: CDK lo inyecta (`ecs-fargate.ts:361`). Dev: comentada | Opc. | ⚠️ (ARN con ID de cuenta) |

### 5.4 Listas de cautela (Tusdatos)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `PROVEEDOR_LISTAS_CAUTELA` | `dummy` (simula), `sagrilaft` (API real), `deshabilitado`. `dummy` está **prohibido en production** (`load_config` y CDK). | `SagrilaftListasConfig`, `load_config()`, `api/dependencies.py` | Dev: `.env`. AWS: contexto CDK `-c proveedorListasCautela` (default `dummy` en staging, `sagrilaft` en prod) | Opc. (default código `dummy`) | — |
| `SAGRILAFT_API_URL` | URL de la API Tusdatos. Con `sagrilaft` es obligatoria. | `SagrilaftListasConfig` | AWS: contexto CDK `-c sagrilaftApiUrl` (si va vacía CDK usa el placeholder `dummy://listas-cautela`) | Obl. solo con `sagrilaft` | — |
| `SAGRILAFT_API_KEY` | API key de Tusdatos. | `SagrilaftListasConfig` | AWS: secreto `sagrilaft_listas_cautela_credentials.api_key`, escrito por `sync_aws_runtime_assets.py --apply` solo con `PROVEEDOR_LISTAS_CAUTELA=sagrilaft` y valor real (ver §9.1, hallazgo 4) | Obl. solo con `sagrilaft` | 🔒 |

## 6. Almacenamiento y Keycloak

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `STORAGE_BACKEND` | `local` (volumen) o `s3`. En staging/prod **solo `s3`** (falla en `load_config` y en `entrypoint.sh`). | `AppConfig.storage_backend` | Dev: `.env`/compose (`local`). AWS: CDK `s3` | Opc. (default `local`) | — |
| `S3_BUCKET` | Bucket de archivos. | `S3Config`, `entrypoint.sh` | AWS: nombre del bucket creado por CDK (SSM) | **Obl. si `s3` en staging/prod**; en dev puede ir vacía | ⚠️ (identifica infraestructura) |
| `KEYCLOAK_URL` | URL interna con la que el backend busca las claves JWKS (en AWS: DNS interno Cloud Map). | `KeycloakConfig.url`, `jwks_uri` | Dev: `.env`. AWS: SSM (`http://keycloak.sagrilaft-{env}.local:8080`) | Opc.; vacía ⇒ integración inactiva | — |
| `KEYCLOAK_REALM` | Realm. | `KeycloakConfig` | CDK `sagrilaft` | Opc. (`sagrilaft`) | — |
| `KEYCLOAK_CLIENT_ID` | Client ID del portal. | `KeycloakConfig` | CDK `sagrilaft-portal` | Opc. (vacío); `configurado` lo exige | — |
| `KEYCLOAK_ISSUER_URL` | URL pública que Keycloak escribe como `iss` en los tokens. | `KeycloakConfig.issuer` | AWS: SSM (`https://{dominioKeycloak}`) | Opc. (si falta usa `KEYCLOAK_URL`) | — |
| `KEYCLOAK_HOSTNAME` | Hostname público de Keycloak (`KC_HOSTNAME`). | compose; `ecs-fargate.ts` | AWS: SSM | Opc. | — |
| `KEYCLOAK_ADMIN` | Usuario admin de la consola. | compose | AWS: secreto `keycloak_admin.username` (CDK, no escrito desde `.env`). `.env.prod`: eliminada el 2026-10-19 | Opc. (`admin`) | ⚠️ |
| `KEYCLOAK_ADMIN_PASSWORD` | Contraseña admin. | compose (obligatoria) | AWS: secreto `keycloak_admin.password`, generado por CDK (32 caracteres). eliminada de `.env.prod` el 2026-10-19; `.env.*` no es su fuente | **Obl.** en compose | 🔒 |
| `KEYCLOAK_DB_URL` | JDBC de la BD de Keycloak. | compose base (`KC_DB_URL`) | AWS: CDK (`ecs-fargate.ts:360`) | Opc. | ⚠️ |
| `KEYCLOAK_DB_USER` | Usuario BD de Keycloak. | compose base | AWS: secreto `db_credentials.username`, generado por CDK. eliminada de `.env.prod` el 2026-10-19; `.env.*` no es su fuente | Obl. en compose | 🔒 |
| `KEYCLOAK_DB_PASSWORD` | Contraseña BD de Keycloak. | ídem | AWS: secreto `db_credentials.password`, generado por CDK y usado por RDS. eliminada de `.env.prod` el 2026-10-19; `.env.*` no es su fuente | Obl. en compose | 🔒 |

## 7. Qué cambia entre desarrollo, staging y producción

Valores **no sensibles** (de las plantillas `.example`, y entre paréntesis el valor del
archivo real cuando difiere). Dominios: staging `*-staging-sagrilaft.ia.blend360.com`;
prod `*sagrilaft.ia.blend360.com`.

| Variable | Desarrollo | Staging | Producción |
|---|---|---|---|
| `APP_ENV` | `development` | `staging` | `production` |
| `STORAGE_BACKEND` | `local` | `s3` | `s3` |
| `S3_BUCKET` | vacío | bucket CDK de staging | bucket CDK de prod (**vacío** en `.env.prod`) |
| `FRONTEND_URL` | `http://localhost:5173` (`.env`: `…:5173,…:5174`) | formulario (real: formulario + portal) | formulario (real: formulario + portal) |
| `VITE_BACKEND_URL` | `http://localhost:8000` (`.env`: `http://backend:8000`) | ejemplo: URL del portal; **real: vacío** | ejemplo: URL del portal; **real: vacío** |
| `KEYCLOAK_URL` | `http://localhost:8080` (`.env`: `http://keycloak:8080`) | ejemplo: URL pública; real: DNS interno | ejemplo: URL pública; real: DNS interno |
| `ZOHO_SIGN_TESTING` | `true` | ejemplo `true`; **real `false`** | `false` |
| `PROVEEDOR_LISTAS_CAUTELA` | `dummy` (`.env`: `deshabilitado`) | ejemplo `dummy`; real `sagrilaft`; CDK default `dummy`; checklist `deshabilitado` | ejemplo `sagrilaft`; real `deshabilitado` |
| `SNS_NOTIFICACIONES_ENABLED` | `false` | ejemplo `true`; real `false` | ejemplo `true`; real `false` |
| `SES_NOTIFICACIONES_ENABLED` | `false` | `true` | `true` |
| `SMTP_FROM` / `SES_EMAIL_ORIGEN` | `no-responder@localhost` / vacío | ejemplo: `no-reply-sagrilaft@…`; real: correo personal | `no-reply-sagrilaft@ia.blend360.com` |
| `SMTP_REPLY_TO` | vacío | `legal@…` | `legal@…` |
| `UVICORN_WORKERS` | `1` (`.env`: 4; compose dev fija 1) | `2` (CDK fija 4) | `4` |
| `TRUSTED_PROXY_IPS` | vacío (compose fija `172.0.0.0/8`) | `REPLACE_*` en ejemplo; real `172.0.0.0/8` | ídem |
| `BEDROCK_MODEL_ID` | real (2026-10-20): `us.amazon.nova-pro-v1:0`, cuenta <CUENTA_AWS> | `REPLACE_*`; decidido: `amazon.nova-pro-v1:0` (`.env.staging` pendiente de alinear) | `REPLACE_*`; real: `amazon.nova-pro-v1:0` |
| `PORTAL_AUTH_DISABLED` | `false` | `false` | `false` |
| `AWS_ACCESS_KEY_ID`/`SECRET` | eliminadas (2026-10-20) | prohibidas | prohibidas |
| `AWS_PROFILE` | `PS-PowerUserAccess-<CUENTA_AWS>` (SSO, 2026-10-20) | no aplica | no aplica |

El resto de variables (`BEDROCK_*` numéricas, `ZOHO_*` de timeouts/reintentos,
`SMTP_PORT`, `SMTP_HOST`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `VITE_RAZON_SOCIAL`,
`VITE_CORREO_DATOS`, `VITE_KEYCLOAK_*`) tienen el mismo valor en los tres ambientes,
salvo los dominios `VITE_*_URL`.

## 8. Manejo de información sensible

- 🔒 **Secretos** (`AWS_*` estáticas, `SECRET_KEY`, `ZOHO_CLIENT_SECRET`,
  `ZOHO_REFRESH_TOKEN`, `ZOHO_WEBHOOK_SECRET`, `SMTP_USER/PASSWORD`,
  `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_*`, `POSTGRES_PASSWORD`, `DATABASE_URL`,
  `SAGRILAFT_API_KEY`): nunca en Git, chats, tickets ni logs. En AWS viven en Secrets
  Manager y se inyectan como secretos ECS; localmente, solo en archivos `.env*` ignorados.
- Los `.env.staging`/`.env.prod` reales **contienen secretos productivos en disco**:
  mantener permisos `600` (hoy solo `.env.prod` los tiene) y rotarlos si el equipo
  se amplía o el archivo se comparte.
- `ZOHO_CLIENT_ID` y el nombre de `AWS_PROFILE` no son secretos por sí solos, pero se
  tratan como credenciales: no publicarlos.
- ⚠️ Los correos y ARNs son datos personales/de infraestructura: no los copie en
  documentación pública.
- `VITE_*` son públicos (van en el bundle).
- Los `.example` deben contener solo marcadores (`REPLACE_*`/`changeme`), nunca valores reales.
- Rotación: generar `SECRET_KEY` con `python3 -c "import secrets; print(secrets.token_hex(32))"`.
  Cambiarla invalida la verificación de reportes de auditoría firmados con la anterior
  **(no verificado el impacto operativo exacto)**.

## 9. Inconsistencias encontradas

Comparación `.env` ↔ `.env.dev.example`, `.env.staging` ↔ `.env.staging.example`,
`.env.prod` ↔ `.env.prod.example` (79 claves distintas en total).

### 9.1 Faltantes y diferencias de claves

| # | Hallazgo |
|---|---|
| 1 | `.env` (52 claves) no tiene 27 que sí están en `.env.dev.example`: los 8 `BEDROCK_*` numéricos, 11 `ZOHO_*` de tiempos/reintentos + `ZOHO_WEBHOOK_SIGNATURE_HEADER`, `JWKS_CACHE_TTL_SECONDS`, `MAX_UPLOAD_SIZE_MB`, `SMTP_REPLY_TO`, `SNS_TOPIC_ARN` (comentada), `VITE_RAZON_SOCIAL`, `VITE_CORREO_DATOS`. Todas tienen default en código, por lo que no rompe, pero `.env` está desactualizado. |
| 2 | **Resuelto (2026-10-20).** `.env` tenía `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` con una clave ya inválida en AWS. Se eliminaron de `.env` y de `docker-compose.yml`; local ahora usa `AWS_PROFILE` + sesión SSO montada por `docker-compose.dev.yml` (`~/.aws/config` y `~/.aws/sso`, nunca `~/.aws/credentials`). Confirmado con `boto3` dentro del contenedor: credenciales por método `sso`, cuenta `<CUENTA_AWS>`. |
| 3 | `.env.staging` y `.env.prod` (45 claves) no tienen 23 claves del ejemplo: 8 `BEDROCK_*`, 11 `ZOHO_*` de tiempos, `MAX_UPLOAD_SIZE_MB`, `PORTAL_AUTH_DISABLED`, `SMTP_REPLY_TO`. Los valores de runtime no salen de estos archivos (§1), así que el impacto es solo documental. |
| 4 | **Corregido.** `sync_aws_runtime_assets.py` ahora escribe `SAGRILAFT_API_KEY` en `sagrilaft_listas_cautela_credentials` si tiene valor real y el secreto ya existe (CDK lo crea). Con `--apply` y cuenta verificada. Antes no lo sincronizaba. |
| 5 | **Corregido.** La versión anterior de `sync_aws_runtime_assets.py` sobrescribía `app_secret`, `db_credentials` y `keycloak_admin` con valores de `.env.prod`, lo que podía desincronizar la contraseña de RDS y la de Keycloak. Ahora esos tres secretos son administrados por CDK y el script nunca los escribe. |
| 6 | `.env.dev.example` deja `JWKS_CACHE_TTL_SECONDS=` y `TRUSTED_PROXY_IPS=` vacías. `autenticacion.py:84` hace `int(os.getenv(..., "300"))`: si la variable llegara vacía al proceso, `int("")` lanzaría `ValueError`. Hoy compose no la inyecta, por lo que no ocurre; conviene eliminarla de la plantilla o dejar `300`. |
| 7 | Variables definidas pero que **compose no inyecta al contenedor** (en dev no tienen efecto aunque se cambien en `.env`): `JWKS_CACHE_TTL_SECONDS`, `MAX_UPLOAD_SIZE_MB`, `SMTP_REPLY_TO`, `SNS_*`, `VITE_RAZON_SOCIAL`, `VITE_CORREO_DATOS`. |
| 8 | `VITE_RAZON_SOCIAL` y `VITE_CORREO_DATOS` los lee también el backend (`exportacion_pdf.py`), pero ni compose ni CDK se los pasan: el PDF usa los defaults del código, p. ej. `HIGH TECH SOFTWARE S.A.S.` (con punto final) frente a `HIGH TECH SOFTWARE S.A.S` de los `.env`. |
| 9 | `PORT_PUBLICO`/`PORT_PORTAL`: `.env` usa 80/81, `.env.dev.example` 5173/5174, default de compose 80/81; y `docker-compose.dev.yml` publica 5173/5174 por su cuenta. El efecto real combinando ambos compose **(no verificado)**. |
| 10 | `.env` apunta a `DATABASE_URL` con host `postgres`, el ejemplo a `localhost`; compose dev ignora ambos y recompone la URL (§3). |
| 11 | **Cambio 2026-10-19.** Se eliminaron de `.env.prod` `SECRET_KEY`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD`, porque ningún script local las leía (solo `docker-compose` de dev y las plantillas `.example`, que no cambian). Sus valores viven en AWS (`app_secret`, `keycloak_admin`, `db_credentials`). Las plantillas `.example` siguen declarándolas, así que `validate_envs.py` sigue aprobando; `.env.prod` ya no las contiene, y eso aparece como faltante si se compara con el ejemplo. |

### 9.2 Diferencias real ↔ ejemplo en staging/prod

- `PROVEEDOR_LISTAS_CAUTELA`: staging real `sagrilaft`, ejemplo `dummy`, CDK `dummy`,
  checklist `deshabilitado`; prod real `deshabilitado`, ejemplo `sagrilaft`. Cuatro fuentes,
  tres valores distintos en staging.
- `ZOHO_SIGN_TESTING`: staging real `false`, ejemplo `true` y CDK `true`; el checklist y
  los criterios confirmados dicen sandbox en staging. Si `.env.staging` se usara como
  fuente, staging consumiría créditos reales de Zoho.
- `BEDROCK_MODEL_ID`: los tres ambientes usan `amazon.nova-pro-v1:0` (verificado 2026-10-20
  contra SSM real de staging y prod, y con invocación real desde local). Claude Sonnet 4.6
  tiene mayor precisión al extraer datos de documentos, pero no se usa en ningún ambiente:
  en local falla por permisos de AWS Marketplace del rol disponible; en staging/prod nunca
  se evaluó cambiarlo. El cambio a `nova-pro-v1:0` en staging no fue una migración
  deliberada: fue efecto colateral de un despliegue hecho por otro motivo (activar el NAT
  Gateway) que usa ese valor como default en `infra/sagrilaft/package.json`. `.env.staging`
  ya se corrigió para reflejar el valor real.
- `KEYCLOAK_URL`: el ejemplo usa la URL pública HTTPS; el real y el CDK usan el DNS
  interno `http://keycloak.sagrilaft-{env}.local:8080`. El ejemplo es el incorrecto.
- `VITE_BACKEND_URL`: ejemplo = URL del portal; real = vacío. El checklist indica vacío.
- `SNS_NOTIFICACIONES_ENABLED`: ejemplo `true`; real y CDK `false`.
- `SMTP_FROM`/`SES_EMAIL_ORIGEN` en `.env.staging` usan un correo personal en vez de
  `no-reply-sagrilaft@…`.
- `.env.prod` aún tiene `S3_BUCKET=` vacío y `SAGRILAFT_API_URL`/`SAGRILAFT_API_KEY`
  con marcador `REPLACE_*`. `.env.staging` conserva `REPLACE_STAGING_SAGRILAFT_API_*` aun con
  `PROVEEDOR_LISTAS_CAUTELA=sagrilaft`: con ese proveedor, `load_config()` aborta
  (`SAGRILAFT_API_URL`/`KEY` requeridas).
- `.env.prod` tiene un comentario "VERIFICAR PARA QUE ES ESTA" sobre `APP_ENV`
  (es la variable de ambiente, ver §2) y cabeceras obsoletas
  ("Reemplazar todos los `REPLACE_*`", "NUNCA subas este archivo").
- `.env.staging`/`.env.prod` mantienen el comentario de `PROVEEDOR_LISTAS_CAUTELA`
  "NUNCA usar dummy… sagrilaft", incoherente con el valor `deshabilitado` de `.env.prod`.
- El validador `validate_envs.py` aprueba los tres ambientes porque solo mira la presencia
  de claves: no detecta nada de lo anterior. Además marca `MAX_UPLOAD_SIZE_MB`,
  `PORTAL_AUTH_DISABLED`, `PROVEEDOR_LISTAS_CAUTELA`, `SAGRILAFT_API_*` como "extras"
  (no están en su lista esperada).

### 9.3 Otras inconsistencias de configuración

- `docker-compose.yml:13` indica `--env-file .env.dev`, pero ese archivo no existe; la
  plantilla pide copiar a `.env`, y `checklist-valores-staging-prod.md` dice que `.env`
  es el estándar.
- `docker-compose.yml` base default `APP_ENV=production` vs `entrypoint.sh` default
  `development` vs backend sin default.
- `docker-compose.yml` base default `PROVEEDOR_LISTAS_CAUTELA=dummy` y
  `TRUSTED_PROXY_IPS=172.0.0.0/8` vs default del `entrypoint.sh` `127.0.0.1`.
- Variables fuera de los `.env` que influyen: `UPLOAD_DIR`, `DATABASE_HOST`,
  `KEYCLOAK_FORMULARIO_URL`, `KEYCLOAK_PORTAL_URL` (build de Keycloak; se leen de `.env.*` o
  `vars.*` de GitHub Actions). No están en los `.example`.

## 10. Estado de la documentación previa

| Documento | Cubre | Brechas |
|---|---|---|
| [Matriz AWS](MATRIZ_AWS_CONFIG.md) | Contrato de secretos y parámetros SSM por servicio. | No explica cada variable ni las de dev; contradicciones de §9.1 (4, 5). `JWKS_CACHE_TTL_SECONDS`, `KEYCLOAK_ADMIN`, `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD` no aparecían en ningún `.md` fuera de `evidencia/` (salvo en este). |
| [Valores por ambiente](checklist-valores-staging-prod.md) | Valores no sensibles preparados. | Revisión del 2026-10-06; difiere de los `.env` reales (§9.2). |
| Este documento | Referencia por variable. | Mantener sincronizado con `configuracion.py` y `config-parameters.ts`. |

Al agregar una variable: declararla en `configuracion.py` (o consumidor), añadirla a los
tres `.example` y a `validate_envs.py`, inyectarla en compose y CDK, y registrarla aquí.
