# Variables de entorno (`.env*`)

Función única: referencia por variable de los archivos `.env`, `.env.dev.example`,
`.env.staging(.example)` y `.env.prod(.example)`: significado, consumo, origen,
diferencias por ambiente, obligatoriedad y sensibilidad.

Elaborado el 2026-10-16 y actualizado con los cambios locales del 2026-11-03 a partir del código (`backend/infrastructure/config/configuracion.py`,
`backend/entrypoint.sh`, `docker-compose*.yml`, `infra/sagrilaft/lib/**`, `scripts/**`,
`frontend/**`). **No contiene valores secretos** (ni contraseñas, tokens, claves, IDs de
cliente OAuth ni IDs de acceso AWS). Los valores concretos no sensibles por ambiente
siguen en [Valores por ambiente](checklist-valores-staging-prod.md) y el contrato de
Secrets Manager/SSM en la [Matriz AWS](MATRIZ_AWS_CONFIG.md).

Las observaciones de AWS y de archivos locales corresponden a la fecha de la consulta; no garantizan el estado actual. Los cambios preparados en el repositorio requieren despliegue para surtir efecto en AWS.

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
| `UVICORN_WORKERS` | Número de procesos Uvicorn. | `backend/entrypoint.sh` (`--workers`) | Dev: compose fija `1`. CDK local prepara `2` en staging y `4` en producción; lo consultado en AWS era `4` en ambos. | Opc. (default 4) | — |
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
| `ZOHO_REDIRECT_URI` | URI enviada al renovar el token OAuth. Su registro y necesidad deben verificarse en Zoho; la ruta configurada no implica que exista un callback en la aplicación. | `ZohoSignConfig`, `zoho_sign_service.py` | Dev: `.env`. AWS: SSM | **Obl.** (falla `validar()`) | — |
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
| `SMTP_REPLY_TO` | Dirección de respuesta. | `SmtpConfig.responder_a` | SSM; CDK local la inyecta en ECS y compose la pasa al contenedor. Cambios locales aún sin desplegar. | Opc. (vacío) | ⚠️ |
| `SES_EMAIL_ORIGEN` | Remitente verificado en SES para alertas internas HTML. | `SesConfig` | AWS: SSM | Opc.; `configurado` exige también `SES_NOTIFICACIONES_ENABLED=true` | ⚠️ |
| `SES_NOTIFICACIONES_ENABLED` | Interruptor de alertas por SES. | `SesConfig.habilitado` | CDK `true`. Compose default `false` | Opc. (`false`) | — |
| `ALERTAS_EMAIL_DESTINATARIO` | Destinatario(s) internos de alertas (lista separada por comas). | `infrastructure/notificaciones/ses_alertas.py:137` | AWS: SSM (contexto `snsAlertasSub`) | Opc.; si está vacía no se envía ("sin destinatarios") | ⚠️ (datos personales) |
| `SNS_NOTIFICACIONES_ENABLED` | Interruptor del adaptador SNS (hoy apagado; SES es el canal). | `SnsConfig.habilitado` | CDK `false` | Opc. (`false`) | — |
| `SNS_TOPIC_ARN` | ARN del topic SNS de alertas. **Administrada por CDK**: ninguna persona la configura; `validate_envs.py` la trata como opcional en los tres entornos (`CDK_MANAGED_KEYS`), no como requerida. | `SnsConfig.topic_arn` | AWS: CDK lo inyecta (`ecs-fargate.ts:361`). Dev: comentada | Opc. (CDK-managed) | ⚠️ (ARN con ID de cuenta) |

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
| `S3_BUCKET` | Bucket de archivos. En AWS CDK lo publica en SSM; compose lo usa si se configura S3 en local. `check_staging_readiness.py` exige su declaración en las plantillas. | `S3Config`, `entrypoint.sh`, compose y validación | AWS: CDK/SSM; local: `.env` | Necesario cuando se usa S3; opcional en `validate_envs.py` | ⚠️ |
| `KEYCLOAK_URL` | URL interna con la que el backend busca las claves JWKS (en AWS: DNS interno Cloud Map). | `KeycloakConfig.url`, `jwks_uri` | Dev: `.env`. AWS: SSM (`http://keycloak.sagrilaft-{env}.local:8080`) | Opc.; vacía ⇒ integración inactiva | — |
| `KEYCLOAK_REALM` | Realm. | `KeycloakConfig` | CDK `sagrilaft` | Opc. (`sagrilaft`) | — |
| `KEYCLOAK_CLIENT_ID` | Client ID del portal. | `KeycloakConfig` | CDK `sagrilaft-portal` | Opc. (vacío); `configurado` lo exige | — |
| `KEYCLOAK_ISSUER_URL` | URL pública que Keycloak escribe como `iss` en los tokens. | `KeycloakConfig.issuer` | AWS: SSM (`https://{dominioKeycloak}`) | Opc. (si falta usa `KEYCLOAK_URL`) | — |
| `KEYCLOAK_HOSTNAME` | Hostname público de Keycloak (`KC_HOSTNAME`). | compose; `ecs-fargate.ts` | AWS: SSM | Opc. | — |
| `KEYCLOAK_ADMIN` | Usuario admin de la consola. | compose | AWS: secreto `keycloak_admin.username` (CDK, no escrito desde `.env`). `.env.prod`: eliminada el 2026-10-19 | Opc. (`admin`) | ⚠️ |
| `KEYCLOAK_ADMIN_PASSWORD` | Contraseña admin. | compose (obligatoria) | AWS: secreto `keycloak_admin.password`, generado por CDK (32 caracteres). eliminada de `.env.prod` el 2026-10-19; `.env.*` no es su fuente | **Obl.** en compose | 🔒 |
| `KEYCLOAK_DB_URL` | JDBC de Keycloak. Compose base lo lee; el archivo de desarrollo lo reemplaza con un valor fijo. | compose base (`KC_DB_URL`) | AWS: CDK (`ecs-fargate.ts`) | Opc. | ⚠️ |
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
| `VITE_BACKEND_URL` | `http://localhost:8000` | ejemplo y real: vacío (mismo origen) | ejemplo y real: vacío (mismo origen) |
| `KEYCLOAK_URL` | `http://localhost:8080` (`.env`: `http://keycloak:8080`) | ejemplo y real: DNS interno | ejemplo y real: DNS interno |
| `ZOHO_SIGN_TESTING` | `true` | ejemplo `true`; **real `false`** | `false` |
| `PROVEEDOR_LISTAS_CAUTELA` | `dummy` (`.env`: `deshabilitado`) | ejemplo y archivo local: `dummy`; CDK local: `dummy` | ejemplo y archivo local: `deshabilitado`; CDK local: `deshabilitado` |
| `SNS_NOTIFICACIONES_ENABLED` | `false` | ejemplo y real `false` | ejemplo y real `false` |
| `SES_NOTIFICACIONES_ENABLED` | `false` | `true` | `true` |
| `SMTP_FROM` / `SES_EMAIL_ORIGEN` | `no-responder@localhost` / vacío | ejemplo: no-reply; archivo local: SMTP no-reply y SES correo personal | no-reply |
| `SMTP_REPLY_TO` | vacío | ejemplo: `legal@…`; ausente del archivo local consultado | ejemplo: `legal@…`; ausente del archivo local consultado |
| `UVICORN_WORKERS` | `1` (`.env`: 4; compose dev fija 1) | CDK local `2`; AWS consultado `4` | CDK local y AWS consultado `4` |
| `TRUSTED_PROXY_IPS` | vacío (compose fija `172.0.0.0/8`) | `REPLACE_*` en ejemplo; real `172.0.0.0/8` | ídem |
| `BEDROCK_MODEL_ID` | opcional en local | ejemplo: marcador; `.env.staging`: perfil de inferencia; decisión: identificador directo | ejemplo: marcador; `.env.prod`: identificador directo |
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

La comparación de claves siguiente conserva hallazgos de la auditoría inicial;
los archivos locales pueden haber cambiado. Las diferencias revisadas aparecen en §9.2.

### 9.1 Faltantes y diferencias de claves

| # | Hallazgo |
|---|---|
| 1 | `.env` (52 claves) no tiene 27 que sí están en `.env.dev.example`: los 8 `BEDROCK_*` numéricos, 11 `ZOHO_*` de tiempos/reintentos + `ZOHO_WEBHOOK_SIGNATURE_HEADER`, `JWKS_CACHE_TTL_SECONDS`, `MAX_UPLOAD_SIZE_MB`, `SMTP_REPLY_TO`, `SNS_TOPIC_ARN` (comentada), `VITE_RAZON_SOCIAL`, `VITE_CORREO_DATOS`. Todas tienen default en código, por lo que no rompe, pero `.env` está desactualizado. |
| 2 | **Resuelto (2026-10-20).** `.env` tenía `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` con una clave ya inválida en AWS. Se eliminaron de `.env` y de `docker-compose.yml`; local ahora usa `AWS_PROFILE` + sesión SSO montada por `docker-compose.dev.yml` (`~/.aws/config` y `~/.aws/sso`, nunca `~/.aws/credentials`). Confirmado con `boto3` dentro del contenedor: credenciales por método `sso`, cuenta `<CUENTA_AWS>`. |
| 3 | `.env.staging` y `.env.prod` (45 claves) no tienen 23 claves del ejemplo: 8 `BEDROCK_*`, 11 `ZOHO_*` de tiempos, `MAX_UPLOAD_SIZE_MB`, `PORTAL_AUTH_DISABLED`, `SMTP_REPLY_TO`. Los valores de runtime no salen de estos archivos (§1), así que el impacto es solo documental. |
| 4 | **Corregido.** `sync_aws_runtime_assets.py` ahora escribe `SAGRILAFT_API_KEY` en `sagrilaft_listas_cautela_credentials` si tiene valor real y el secreto ya existe (CDK lo crea). Con `--apply` y cuenta verificada. Antes no lo sincronizaba. |
| 5 | **Corregido.** La versión anterior de `sync_aws_runtime_assets.py` sobrescribía `app_secret`, `db_credentials` y `keycloak_admin` con valores de `.env.prod`, lo que podía desincronizar la contraseña de RDS y la de Keycloak. Ahora esos tres secretos son administrados por CDK y el script nunca los escribe. |
| 6 | **Corregido en la plantilla:** `JWKS_CACHE_TTL_SECONDS=300` evita convertir una cadena vacía a entero si se inyecta. Compose todavía no la pasa al backend. |
| 7 | Variables definidas pero que **compose no inyecta al contenedor** (en dev no tienen efecto aunque se cambien en `.env`): `JWKS_CACHE_TTL_SECONDS`, `MAX_UPLOAD_SIZE_MB`, `SNS_*`, `VITE_RAZON_SOCIAL`, `VITE_CORREO_DATOS`. `SMTP_REPLY_TO` sí se pasa con el cambio local. |
| 8 | El PDF usa los valores legales predeterminados del backend, pues compose y CDK no le inyectan `VITE_RAZON_SOCIAL` ni `VITE_CORREO_DATOS`. Los defaults del PDF y frontend ya coinciden con los datos confirmados. |
| 9 | `PORT_PUBLICO`/`PORT_PORTAL`: `.env` usa 80/81, `.env.dev.example` 5173/5174, default de compose 80/81; y `docker-compose.dev.yml` publica 5173/5174 por su cuenta. El efecto real combinando ambos compose **(no verificado)**. |
| 10 | `.env` apunta a `DATABASE_URL` con host `postgres`, el ejemplo a `localhost`; compose dev ignora ambos y recompone la URL (§3). |
| 11 | **Cambio 2026-10-19.** Se eliminaron de `.env.prod` `SECRET_KEY`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD`, porque ningún script local las leía (solo `docker-compose` de dev y las plantillas `.example`, que no cambian). Sus valores viven en AWS (`app_secret`, `keycloak_admin`, `db_credentials`). Las plantillas `.example` siguen declarándolas, así que `validate_envs.py` sigue aprobando; `.env.prod` ya no las contiene, y eso aparece como faltante si se compara con el ejemplo. |

### 9.2 Diferencias y decisiones pendientes en staging/prod

- Listas de cautela: las plantillas, los archivos locales consultados y los defaults de CDK locales reflejan `dummy` en staging y `deshabilitado` en producción. Aún hay que verificar la configuración efectiva antes de desplegar.
- Zoho: el `.env.staging` consultado tenía `ZOHO_SIGN_TESTING=false`; la decisión es `true` en staging y `false` en producción. El archivo local no configura por sí solo ECS.
- Bedrock: se decidió `amazon.nova-pro-v1:0` en ambos ambientes. El `.env.staging` consultado contiene un perfil de inferencia; debe conciliarse sin asumir que es el valor efectivo de ECS.
- Remitente: en el `.env.staging` consultado `SMTP_FROM` ya usa no-reply y `SES_EMAIL_ORIGEN` contiene otro correo. La decisión es utilizar no-reply para las rutas de SAGRILAFT; verificar SSM y tareas antes de aplicar cambios.
- Las plantillas usan DNS interno para `KEYCLOAK_URL`, `VITE_BACKEND_URL` vacío y `SNS_NOTIFICACIONES_ENABLED=false`. Estos cambios son de referencia; no actualizan AWS.
- `validate_envs.py` comprueba presencia de claves en plantillas, no sus valores ni la configuración efectiva de AWS.

### 9.3 Otras inconsistencias de configuración

- `docker-compose.yml:13` indica `--env-file .env.dev`, pero ese archivo no existe; la
  plantilla pide copiar a `.env`, y `checklist-valores-staging-prod.md` dice que `.env`
  es el estándar.
- `docker-compose.yml` base default `APP_ENV=production` vs `entrypoint.sh` default
  `development` vs backend sin default.
- `docker-compose.yml` base default `PROVEEDOR_LISTAS_CAUTELA=dummy` y
  `TRUSTED_PROXY_IPS=172.0.0.0/8` vs default del `entrypoint.sh` `127.0.0.1`.
- Variables fuera de los `.env` que influyen: `UPLOAD_DIR`, `DATABASE_HOST`,
  `KEYCLOAK_FORMULARIO_URL`, `KEYCLOAK_PORTAL_URL` (build de Keycloak; el publicador puede derivarlas de las URL de formulario y portal, incluso cuando lee SSM). No están en los `.example`.

## 10. Estado de la documentación previa

| Documento | Cubre | Brechas |
|---|---|---|
| [Matriz AWS](MATRIZ_AWS_CONFIG.md) | Contrato de secretos y parámetros SSM por servicio. | No explica cada variable ni las de dev; contradicciones de §9.1 (4, 5). `JWKS_CACHE_TTL_SECONDS`, `KEYCLOAK_ADMIN`, `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD` no aparecían en ningún `.md` fuera de `evidencia/` (salvo en este). |
| [Valores por ambiente](checklist-valores-staging-prod.md) | Valores no sensibles preparados. | Revisión del 2026-10-06; difiere de los `.env` reales (§9.2). |
| Este documento | Referencia por variable. | Mantener sincronizado con `configuracion.py` y `config-parameters.ts`. |

Al agregar una variable, documentar su consumidor y fuente; actualizar configuración, plantillas, validación e inyección solo en los ambientes donde corresponda.


---

# Configuración: decisiones y preparación de implementación

Estado: cambios locales preparados para revisión. No se han desplegado ni se han
modificado AWS, GitHub o la configuración de Keycloak. Las pruebas de correo
reales y la publicación de imágenes requieren autorización posterior.

## Decisiones

| Tema | Decisión |
|---|---|
| Listas de cautela | Staging `dummy`; producción `deshabilitado`. Preparar el proveedor real primero en staging cuando existan credenciales. |
| Zoho | Staging modo pruebas; producción modo real. Las credenciales OAuth compartidas siguen pendientes de revisión. |
| Bedrock | Identificador directo `amazon.nova-pro-v1:0` en ambos ambientes. |
| Workers | Staging 2; producción conserva 4, pendiente comparación de carga. |
| Alarmas de staging | Notificar activación y recuperación de las tres alarmas al tema SNS del stack. |
| Correo | Remitente no-reply; `Reply-To` `legal@blend360.com` en SMTP y SES. Zoho Sign administra los correos de firma por separado. |
| Expedientes | Conservar el destinatario temporal actual hasta que se confirmen las 11 personas y se autorice su actualización. |
| Datos legales | `HIGH TECH SOFTWARE S.A.S` y `administrativocol@blend360.com`; este correo es independiente del `Reply-To`. |
| Parámetro `PORTAL_URL` | Conservar. No se ha descartado un consumidor externo. |
| Builds GitHub | Ambientes `staging` y `production`; parámetros de infraestructura desde SSM del ambiente. |

## Keycloak efectivo, consulta de solo lectura

El cliente `sagrilaft-portal` existe y está habilitado en ambos ambientes como
cliente público OIDC, con flujo estándar activo y flujos directo e implícito
desactivados. Las redirecciones permiten el portal (raíz y rutas) y las rutas
del formulario del ambiente; `Web Origins` contiene los orígenes exactos de
ambos. Coinciden con SSM y con los dominios actuales. El frontend solicita PKCE
`S256`; el atributo de obligatoriedad PKCE no estaba definido explícitamente
en el cliente. No se ha probado un inicio de sesión interactivo ni cambiado el
cliente. `clientAuthenticatorType` figura como `client-secret` en la respuesta
administrativa, mientras `publicClient=true`; no se infiere por ese campo aislado
que el navegador deba tener una credencial.

## Cambios locales y dependencias

- El cambio local prepara la inyección de `SMTP_REPLY_TO` desde SSM; SMTP lo añade
  al MIME y SES lo transmite como `ReplyToAddresses`. Compose lo pasa si existe.
- CDK prepara 2 workers en staging, proveedor dummy por defecto en staging y
  deshabilitado por defecto en producción. `deploy:staging` ya no fuerza el
  proveedor deshabilitado. Los planes de release pasan el contexto explícito y
  deben incluir el valor acordado: los valores de contexto prevalecen.
- Los jobs del workflow seleccionan `staging` o `production`; push a main
  conserva la publicación de producción y `workflow_dispatch` permite elegir.
  El nombre `production` se traduce a `prod` para AWS. Es publicación de
  imágenes, no despliegue. Las imágenes y tags existentes son inmutables.
- El publicador comprueba la cuenta, lee seis parámetros SSM no secretos y
  construye los argumentos sin duplicar las URL en GitHub. Los valores legales
  confirmados son defaults explícitos del publicador. El PDF y el frontend
  comparten el texto confirmado como default, pero su configuración sigue en
  código distinto; esto no constituye una fuente técnica única para ese texto.
- El rol GitHub inspeccionado no tiene una autorización identificada para
  `ssm:GetParameters` sobre los parámetros del proyecto. La simulación IAM fue
  denegada; la lectura de políticas mostró permiso SSM limitado a parámetros
  públicos de ECS. La plantilla `infra/sagrilaft/policies/github-build-ssm.template.json`
  describe el permiso mínimo propuesto; sustituir marcadores y revisar límites,
  políticas de sesión y SCP antes de autorizar su aplicación.
- Los ambientes de GitHub aún no existen. Esto no impide preparar ni hacer
  commits locales; antes de integrar o ejecutar el workflow que publica imágenes
  hay que crearlos y revisar sus restricciones y los permisos SSM. El patrón actual de confianza OIDC
  del rol coincide con ambos sujetos de ambiente, pero es amplio (`repo:ai-scm/*`);
  conviene evaluar su alcance sin asumir que los demás permisos son suficientes.
- `deploy_release.py` solo admite transiciones de imagen/SHA en su modo normal;
  rechazará los cambios de parámetros, alarmas y Task Definitions de este plan.
  No se ha relajado esa protección. Se requiere un procedimiento de cambio
  de infraestructura con diff aprobado, compatible con el despliegue y reversión,
  antes de aplicar estas modificaciones.
- Las copias locales `.env.staging`/`.env.prod` y el flujo de
  carga de credenciales siguen pendientes de limpieza. No retirar las entradas
  mientras el sincronizador y las validaciones aún las requieran.

### Recuperación de una publicación interrumpida

El workflow guarda el manifiesto parcial como artefacto identificado por SHA,
ejecución e intento. Un reintento normal no reutiliza esa evidencia y se detiene
si encuentra tags inmutables existentes. Para recuperarlo, una persona autorizada
debe descargar el artefacto de esa ejecución, revisar su ambiente, cuenta,
región, SHA, configuraciones y digests contra ECR y aprobar expresamente su
reutilización. Con el mismo commit limpio y los permisos necesarios, el publicador
permite pasar ese archivo mediante `--reuse-manifest`, junto con `--manifest` para
un archivo nuevo fuera del repositorio. El publicador valida la evidencia y no
sobrescribe tags. Esta recuperación requiere acceso AWS y no se ha ejecutado;
la operación y el despliegue requieren aprobación independiente.

## Comprobaciones para una ejecución futura

1. Revisar los diffs local y CloudFormation por separado, con el contexto
   completo real, sin alterar el destinatario SNS ni `ALERTAS_EMAIL_DESTINATARIO`.
2. Aprobar ambientes GitHub, permisos mínimos y el procedimiento de despliegue.
3. Aplicar primero staging y renovar tareas para recibir los parámetros.
4. Probar correo SMTP y SES únicamente con destinatarios autorizados; validar
   encabezados `From` y `Reply-To`, alarma y recuperación. No enviar a las 11
   personas antes de su confirmación.
5. Comparar 2 y 4 workers en staging y validar login interactivo y flujos de
   Keycloak con cuentas de prueba; revisar después el cambio de producción.
6. Con evidencia y aprobación separada, proceder en producción. No eliminar
   `PORTAL_URL` ni modificar destinatarios de expedientes en esta ejecución.

## Comparación local con los stacks consultados

Se sintetizó CDK en directorios temporales usando los valores y etiquetas
observados al consultar AWS. La comparación estructural, sin metadata, no es
un Change Set ni garantiza ausencia de drift o reemplazos. Antes de aplicar se
debe repetir con el contexto y la release exactos y revisar el Change Set.

La comparación anterior identificó cambios en alarmas, parámetros, Task
Definitions y políticas de ejecución. Repetirla con los valores y el código
vigentes; revisar especialmente el permiso de lectura de `SMTP_REPLY_TO`, IAM
y posibles reemplazos antes de autorizar un despliegue.
