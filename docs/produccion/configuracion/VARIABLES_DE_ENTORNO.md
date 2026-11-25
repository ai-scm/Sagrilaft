# Variables de entorno (`.env*`)

Referencia por variable de los archivos `.env`, `.env.dev.example`,
`.env.staging(.example)` y `.env.prod(.example)`: significado, consumo, origen,
diferencias por ambiente, obligatoriedad y sensibilidad.

Elaborado el 2026-10-16 y revisado el 2026-11-24 a partir del código (`backend/infrastructure/config/configuracion.py`,
`backend/entrypoint.sh`, `docker-compose*.yml`, `infra/sagrilaft/lib/**`, `scripts/**`,
`frontend/**`); los datos de AWS se corrigieron contra el código el 2026-11-23.
**No contiene valores secretos.** Los valores que usa AWS y los secretos están en
[Configuración en AWS](MATRIZ_AWS_CONFIG.md).

Las observaciones de AWS y de archivos locales corresponden a la fecha de la consulta; no garantizan el estado actual. Los cambios preparados en el repositorio requieren despliegue para surtir efecto en AWS.

## 1. Cómo se usa cada archivo (léase antes)

| Archivo | Ambiente | ¿Qué hace realmente? | En Git |
|---|---|---|---|
| `.env` | Desarrollo local | Lo lee Docker Compose (sustitución `${VAR}` en `docker-compose.yml` + `docker-compose.dev.yml`). Es el único archivo que alimenta un runtime directamente. | Ignorado (`.gitignore`) |
| `.env.dev.example` | Desarrollo | Plantilla de referencia. **Confirmado 2026-10-20: no es necesario copiarla a `.env` en el día a día** — `.env` ya existe, está poblado y es la fuente que usa Docker Compose. Solo sirve para armar un `.env` desde cero (onboarding) o para ver qué variable existe y su comentario. | Versionado |
| `.env.staging` / `.env.prod` | Staging / producción | **No son runtime.** Los consumen solo scripts de despliegue: `scripts/despliegue/build_and_push_ecr_images.py` (args de build `VITE_*`, `AWS_REGION`, `KEYCLOAK_*_URL`) y `scripts/aws/sync_aws_runtime_assets.py` (escribe en Secrets Manager solo las credenciales externas a CDK: Zoho y, si aplica, la API de listas; nunca `app_secret`, `db_credentials` ni `keycloak_admin`). SMTP no pasa por estos archivos: `smtp_credentials` se carga en la consola de AWS. | Ignorados (`.gitignore`, patrón `.env.*`) |
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
| `UVICORN_WORKERS` | Número de procesos Uvicorn. | `backend/entrypoint.sh` (`--workers`) | Dev: compose fija `1`. AWS: CDK fija `4` en staging y producción (un cambio a `2` en staging se revirtió el 2026-11-03, commit `750ceb2`). | Opc. (default 4) | — |
| `TRUSTED_PROXY_IPS` | Red interna desde la que llegan las visitas a través del balanceador. Solo si una conexión viene de esa red, el backend lee la IP real del visitante que el balanceador le adjunta. Con esa IP se cuentan los intentos por persona y se anota quién hizo cada cosa en los registros de seguridad. Admite una o varias redes separadas por coma (por ejemplo `10.0.0.0/16`). Si el valor está mal escrito, el backend no arranca. | `backend/api/ip_cliente.py` | Local: `172.0.0.0/8` (red de Docker). AWS: la red de la VPC (`10.0.0.0/16`), que CDK toma sola | Opc. (default `127.0.0.1`) | ✅ |
| `SECRET_KEY` | Clave HMAC-SHA256 para firmar reportes de auditoría. | `AppConfig.secret_key` (`os.environ["SECRET_KEY"]`); compose base la exige | Dev: `.env`. `.env.prod`: eliminada el 2026-10-19 (sin consumidor local). AWS: secreto `app_secret.secret_key` (CDK lo genera de 64 caracteres) | **Obl.** (sin default; `KeyError` si falta) | 🔒 |
| `MAX_UPLOAD_SIZE_MB` | Tope de tamaño de archivos subidos. | `AppConfig.max_upload_mb` | AWS: CDK fija `15` en `ecs-fargate.ts`. Dev: **no se inyecta**  | Opc. (default 15) | — |
| `JWKS_CACHE_TTL_SECONDS` | Segundos de caché de las claves JWKS de Keycloak. | `api/middleware/autenticacion.py` | Solo documentada en `.env.dev.example` (vacía) y **no inyectada por compose ni CDK** | Opc. (default 300). Vacía rompe el arranque  | — |
| `PORTAL_AUTH_DISABLED` | `true` desactiva la autenticación del portal interno (solo desarrollo). | `autenticacion.py` (aborta si es `true` fuera de `development/local/test`) | Dev: compose (`${PORTAL_AUTH_DISABLED:-true}`). AWS: no se define | Opc. (sin definir ⇒ autenticación activa) | — (riesgo de seguridad si es `true`) |

## 3. Base de datos y puertos (solo desarrollo)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `DATABASE_URL` | URL SQLAlchemy de PostgreSQL. | `configuracion.py:_require_db_url`, `entrypoint.sh`, `alembic/env.py` | Dev: compose dev la **reconstruye** con `POSTGRES_*` y el host `postgres` (el valor del `.env` se ignora). AWS: el `command` ECS la compone con el secreto `db_credentials` y el host RDS (`ecs-fargate.ts`) | **Obl.** | 🔒 (lleva contraseña) |
| `POSTGRES_DB` | Nombre de la BD del contenedor Postgres. | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | — |
| `POSTGRES_USER` | Usuario de Postgres (también usado por Keycloak en dev). | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | ⚠️ |
| `POSTGRES_PASSWORD` | Contraseña de Postgres (también Keycloak en dev). | `docker-compose.dev.yml` | `.env` | **Obl. en dev** | 🔒 |
| `PORT_PUBLICO` | Puerto host del formulario público. | `docker-compose.yml` (`${PORT_PUBLICO:-80}:8080`) | `.env` | Opc. (default 80) | — |
| `PORT_PORTAL` | Puerto host del portal interno. | `docker-compose.yml` (default 81) | `.env` | Opc. (default 81) | — |

## 4. Frontend y CORS

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `FRONTEND_URL` | Orígenes CORS permitidos (lista separada por comas). También su primer elemento alimenta `KEYCLOAK_FORMULARIO_URL` en el build de Keycloak. | `AppConfig.frontend_urls`, `build_and_push_ecr_images.py` | Dev: `.env`. AWS: SSM (`https://{dominio},https://{dominioPortal}`) | **Obl. en staging/prod** (`load_config` falla); en dev default `http://localhost:5173`. Compose base la exige | — |
| `PORTAL_INTERNO_URL` | URL base del portal; se usa en enlaces de correos de alerta. | `AppConfig.portal_interno_url` | Dev: `.env`. AWS: SSM (`https://{dominioPortal}`) | **Obl.** (sin default) | — |
| `VITE_BACKEND_URL` | Origen del backend para el frontend. **Vacío = mismo origen (`/api` relativo)**, lo que usan staging/prod. En dev es el *target* del proxy de Vite. | `vite.config.js` (ambas apps), Dockerfiles (build arg), `build_and_push_ecr_images.py` (la clave debe existir; vacío permitido) | Dev: `.env`. Build AWS: `.env.staging`/`.env.prod` | Obl. como clave en el build; valor vacío válido | — |
| `VITE_PORTAL_INTERNO_URL` | URL del portal embebida en el build del formulario público (enlaces cruzados) y fallback en Keycloak. | `formulario-publico/src/App.jsx`, Dockerfile, build script, CI | `.env*` / CI (`vars.*`) | **Obl.** en el build script | — |
| `VITE_KEYCLOAK_URL` | URL pública de Keycloak para el login del portal. Vacía en dev ⇒ el frontend no redirige al login. | `portal-interno/src/keycloak.js`, `main.jsx` | ídem | **Obl.** en build staging/prod | — |
| `VITE_KEYCLOAK_REALM` | Realm Keycloak del portal. | `keycloak.js` | ídem | Opc. (default `sagrilaft`) | — |
| `VITE_KEYCLOAK_CLIENT_ID` | Client ID Keycloak del portal. | `keycloak.js` | ídem | Opc. (default `sagrilaft-portal`) | — |
| `VITE_RAZON_SOCIAL` | Razón social en textos legales (Habeas Data). | `formulario-publico/src/config/textos-legales.js`, build script y **backend** `services/formulario/exportacion_pdf.py` | Build: `.env*`. Backend: valores por defecto del código | Opc. (defaults en código) | — |
| `VITE_CORREO_DATOS` | Correo para ejercer derechos de Habeas Data. | `textos-legales.js`, `exportacion_pdf.py` | ídem | Opc. (default en código) | ⚠️ (correo corporativo) |

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

**Modelo en desarrollo local (comprobado el 2026-10-20 con el perfil SSO del equipo):**
`claude-sonnet-4-6` falla con `AccessDeniedException` (permisos de AWS Marketplace); el
perfil de inferencia `us.amazon.nova-pro-v1:0` sí funciona. El `BEDROCK_MODEL_ID` del
`.env` local debe ser uno al que el perfil SSO tenga acceso.

### 5.2 Zoho Sign (firma electrónica)

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `ZOHO_CLIENT_ID` | Client ID OAuth de Zoho. | `ZohoSignConfig.validar()` | Zoho API Console. AWS: secreto `zoho_credentials.client_id` (subido con `sync_aws_runtime_assets.py`) | **Obl.** (falla `validar()`) | 🔒 (tratar como credencial) |
| `ZOHO_CLIENT_SECRET` | Secret OAuth. | ídem | secreto `zoho_credentials.client_secret` | **Obl.** | 🔒 |
| `ZOHO_REFRESH_TOKEN` | Refresh token OAuth. | ídem | secreto `zoho_credentials.refresh_token` | **Obl.** | 🔒 |
| `ZOHO_REDIRECT_URI` | URI enviada al renovar el token OAuth. Su registro y necesidad deben verificarse en Zoho; la ruta configurada no implica que exista un callback en la aplicación. | `ZohoSignConfig`, `zoho_sign_service.py` | Dev: `.env`. AWS: SSM | **Obl.** (falla `validar()`) | — |
| `ZOHO_WEBHOOK_SECRET` | Secreto HMAC del webhook de Zoho. | `FirmaService` (valida firma del webhook), `routers/webhooks.py` | secreto `zoho_credentials.webhook_secret` | Opc. al arrancar; el webhook falla con `RuntimeError` si falta | 🔒 |
| `ZOHO_WEBHOOK_SIGNATURE_HEADER` | Nombre del header con la firma. | `ZohoSignConfig` | CDK `X-ZS-WEBHOOK-SIGNATURE` | Opc. (ese valor) | — |
| `ZOHO_SIGN_TESTING` | `true` = modo prueba de Zoho: marca de agua, sin validez legal y sin consumir créditos. | `ZohoSignConfig.modo_prueba` | CDK: contexto `-c zohoSignTesting`; sin él, `false` en `prod` y `true` en el resto. Los scripts `*:prod` de `package.json` pasan `true` desde el 2026-11-25, mientras se termina de validar. Dev: compose default `true` | Opc. (default código `false`) | — |
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
| `SMTP_USER` | Usuario SMTP de SES. | `SmtpConfig` | Local: `.env` (Compose). Staging/prod: secreto `smtp_credentials.username` vía ECS `secrets:`; no se declara en `.env.staging`/`.env.prod` | Opc. (vacío ⇒ sin SMTP) | 🔒 |
| `SMTP_PASSWORD` | Contraseña SMTP de SES. | ídem | Local: `.env` (Compose). Staging/prod: secreto `smtp_credentials.password` vía ECS `secrets:`; no se declara en `.env.staging`/`.env.prod` | ídem | 🔒 |
| `SMTP_FROM` | Remitente visible para contrapartes. | `SmtpConfig.remitente` | AWS: SSM (= `sesEmailOrigen`, contexto CDK) | Opc. (vacío) | ⚠️ |
| `SMTP_REPLY_TO` | Dirección de respuesta. | `SmtpConfig.responder_a` | AWS: SSM (`legal@blend360.com`). Dev: compose la pasa al contenedor. | Opc. (vacío) | ⚠️ |
| `SES_EMAIL_ORIGEN` | Remitente verificado en SES para alertas internas HTML. | `SesConfig` | AWS: SSM | Opc.; `configurado` exige también `SES_NOTIFICACIONES_ENABLED=true` | ⚠️ |
| `SES_NOTIFICACIONES_ENABLED` | Interruptor de alertas por SES. | `SesConfig.habilitado` | CDK `true`. Compose default `false` | Opc. (`false`) | — |
| `ALERTAS_EMAIL_DESTINATARIO` | Destinatario(s) internos de alertas (lista separada por comas). | `infrastructure/notificaciones/ses_alertas.py` | AWS: SSM (contexto `snsAlertasSub`) | Opc.; si está vacía no se envía ("sin destinatarios") | ⚠️ (datos personales) |
| `SNS_NOTIFICACIONES_ENABLED` | Interruptor del adaptador SNS (hoy apagado; SES es el canal). | `SnsConfig.habilitado` | CDK `false` | Opc. (`false`) | — |
| `SNS_TOPIC_ARN` | ARN del topic SNS de alertas. **Administrada por CDK**: ninguna persona la configura; `validate_envs.py` la trata como opcional en los tres entornos (`CDK_MANAGED_KEYS`), no como requerida. | `SnsConfig.topic_arn` | AWS: CDK lo inyecta (`ecs-fargate.ts`). Dev: comentada | Opc. (CDK-managed) | ⚠️ (ARN con ID de cuenta) |

### 5.4 Listas cautelares

El módulo y todas sus variables se documentan en
[Operación del módulo de listas](../../listas/OPERACION_PRUEBAS_Y_PENDIENTES.md#1-puesta-en-marcha-local)
y [Arquitectura, sección 7](../../listas/ARQUITECTURA_LISTAS.md#7-selección-de-modalidad-y-configuración).
Aquí solo se resume lo que afecta a los ambientes.

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `LISTAS_IMPLEMENTACION` | Modalidad: `deshabilitado`, `simulado`, `archivos` o `externo` (Tusdatos). Manda sobre la variable heredada. En **production** `load_config()` rechaza cualquier valor distinto de `deshabilitado`. `archivos` solo funciona en `development`/`test` | `SagrilaftListasConfig` | Dev: Compose (default `deshabilitado`). AWS: no se usa; manda la heredada | Opc. Sin esta variable ni la heredada: `deshabilitado` | — |
| `PROVEEDOR_LISTAS_CAUTELA` | Variable heredada, traducida: `dummy` → `simulado`, `sagrilaft` → `externo`, `deshabilitado`. Si contradice a `LISTAS_IMPLEMENTACION`, la aplicación no arranca | `SagrilaftListasConfig`, `api/dependencies.py` | Dev: el Compose la deja vacía. AWS: SSM, desde el contexto CDK `-c proveedorListasCautela` (sin contexto: `dummy` en staging y `deshabilitado` en producción) | Opc. | — |
| `LISTAS_TUSDATOS_URL` | Dirección de Tusdatos | Cliente de Tusdatos | AWS: SSM (`https://dash-board.tusdatos.co`) | Obl. con `externo` | — |
| `LISTAS_TUSDATOS_TOKEN` / `_USUARIO` / `_CLAVE` | Credenciales de Tusdatos: token en producción; usuario y clave en el sandbox | Cliente de Tusdatos | AWS: secreto `tusdatos_credentials` (hoy vacío) | Obl. con `externo` | 🔒 |
| `LISTAS_CUSTODIA_BACKEND` / `LISTAS_CUSTODIA_S3_PREFIJO` | Dónde se guardan los informes de las consultas | Custodia de listas | AWS: SSM (`s3`, `listas/custodia/`). Dev: `LISTAS_CUSTODIA_DIRECTORIO` | Opc. | — |
| `SAGRILAFT_API_URL` / `SAGRILAFT_API_KEY` | Restos del circuito **retirado**; ya no se usan para arrancar | — | AWS: SSM (`dummy://listas-cautela`) y secreto `sagrilaft_listas_cautela_credentials` | No | 🔒 (la llave) |

Las demás variables `LISTAS_*` (escenario del simulador, administración, fuentes,
políticas y custodia) solo se usan en local y no tienen origen en AWS.

## 6. Almacenamiento y Keycloak

| Variable | Qué es | Dónde se usa | Origen | Obligatoriedad / default | Sens. |
|---|---|---|---|---|---|
| `STORAGE_BACKEND` | `local` (volumen) o `s3`. En staging/prod **solo `s3`** (falla en `load_config` y en `entrypoint.sh`). | `AppConfig.storage_backend` | Dev: `.env`/compose (`local`). AWS: CDK `s3` | Opc. (default `local`) | — |
| `S3_BUCKET` | Bucket de archivos, **solo staging/producción**. Fuente única: CDK → SSM (`/sagrilaft/{env}/config/S3_BUCKET`, `config-parameters.ts`) → ECS como `secrets:` (`ecs-fargate.ts`). No se declara en ningún `.env*` ni `.env*.example` (eliminada el 2026-11-03): ningún flujo la lee de ahí. En desarrollo no se usa: con `STORAGE_BACKEND=local` el backend guarda en disco (`LocalStorage`). | `S3Config`, `entrypoint.sh` (solo staging/production) | AWS: CDK/SSM | Obl. en staging/prod cuando `STORAGE_BACKEND=s3` (lo garantiza CDK); no aplica en dev | ⚠️ |
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
| `S3_BUCKET` | no aplica (no declarada; `STORAGE_BACKEND=local`) | no declarada (CDK la gestiona en SSM) | no declarada (CDK la gestiona en SSM) |
| `FRONTEND_URL` | `http://localhost:5173` (`.env`: `…:5173,…:5174`) | formulario (real: formulario + portal) | formulario (real: formulario + portal) |
| `VITE_BACKEND_URL` | `http://localhost:8000` | ejemplo y real: vacío (mismo origen) | ejemplo y real: vacío (mismo origen) |
| `KEYCLOAK_URL` | `http://localhost:8080` (`.env`: `http://keycloak:8080`) | ejemplo y real: DNS interno | ejemplo y real: DNS interno |
| `ZOHO_SIGN_TESTING` | `true` | ejemplo `true`; **real `false`** | `true` mientras se valida (CDK `-c zohoSignTesting=true`); `false` al salir con firmas reales |
| `PROVEEDOR_LISTAS_CAUTELA` | ejemplo `dummy`; `docker-compose.dev.yml` la fuerza a vacía y usa `LISTAS_IMPLEMENTACION` (default `deshabilitado`) | ejemplo y archivo local: `dummy`; CDK sin contexto: `dummy` | ejemplo y archivo local: `deshabilitado`; CDK sin contexto: `deshabilitado` |
| `SNS_NOTIFICACIONES_ENABLED` | `false` | ejemplo y real `false` | ejemplo y real `false` |
| `SES_NOTIFICACIONES_ENABLED` | `false` | `true` | `true` |
| `SMTP_FROM` / `SES_EMAIL_ORIGEN` | `no-responder@localhost` / vacío | ejemplo: no-reply; archivo local: SMTP no-reply y SES correo personal | no-reply |
| `SMTP_REPLY_TO` | vacío | ejemplo: `legal@…`; ausente del archivo local consultado | ejemplo: `legal@…`; ausente del archivo local consultado |
| `UVICORN_WORKERS` | `1` (`.env`: 4; compose dev fija 1) | `4` (CDK) | `4` (CDK) |
| `TRUSTED_PROXY_IPS` | vacío (compose fija `172.0.0.0/8`) | `REPLACE_*` en ejemplo; real: la red de la VPC (`10.0.0.0/16`) | ídem |
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
  `ZOHO_REFRESH_TOKEN`, `ZOHO_WEBHOOK_SECRET`, `SMTP_USER/PASSWORD` (en `.env` local),
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

## 9. Detalles que pueden confundir

Comprobados en los archivos versionados el 2026-11-24:

- `docker-compose.yml` dice en un comentario `--env-file .env.dev`, pero ese archivo no
  existe: se usa `.env`.
- `APP_ENV` tiene tres valores por defecto distintos: `production` en
  `docker-compose.yml`, `development` en `entrypoint.sh` y ninguno en el backend.
- `docker-compose.yml` pone por defecto `PROVEEDOR_LISTAS_CAUTELA=dummy` y
  `TRUSTED_PROXY_IPS=172.0.0.0/8` (la red de Docker); la aplicación, sin variable, usa
  `127.0.0.1`.
- Compose no pasa al contenedor `JWKS_CACHE_TTL_SECONDS`, `MAX_UPLOAD_SIZE_MB`,
  `VITE_RAZON_SOCIAL` ni `VITE_CORREO_DATOS`: en local se usan los valores por defecto
  del código, aunque se cambien en `.env`. El PDF del formulario también usa los valores
  por defecto de razón social y correo, que coinciden con los del frontend.
- `.env.staging` y `.env.prod` tienen menos claves que sus plantillas. No afecta a AWS,
  porque los valores de los ambientes no salen de esos archivos (sección 1).
- Las plantillas `.example` todavía declaran `SECRET_KEY`, `KEYCLOAK_ADMIN*` y
  `KEYCLOAK_DB_*`, que se quitaron de `.env.prod` el 2026-10-19 porque viven en AWS.
- `validate_envs.py` solo comprueba que las claves existan en las plantillas, no sus
  valores ni lo que hay en AWS.
- Variables que influyen y no están en los `.example`: `UPLOAD_DIR`, `DATABASE_HOST`,
  `KEYCLOAK_FORMULARIO_URL` y `KEYCLOAK_PORTAL_URL` (las dos últimas las puede derivar
  el publicador de imágenes de las URL del formulario y del portal).

## 10. Relación con otros documentos

Este documento explica los archivos `.env`. Los valores que usa AWS, los secretos y
quién escribe cada uno están en [Configuración en AWS](MATRIZ_AWS_CONFIG.md).

Al agregar una variable, documentar quién la usa y de dónde sale su valor, y
actualizar la configuración, las plantillas, la validación y la inyección solo en los
ambientes que corresponda.
