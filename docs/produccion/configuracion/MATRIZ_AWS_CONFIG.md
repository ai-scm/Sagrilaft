# Configuración en AWS: parámetros y secretos

Este documento dice qué configuración usa SAGRILAFT en AWS, cuánto vale en cada
ambiente, quién la escribe y dónde se guarda. Es la única fuente para esos datos:
los demás documentos enlazan aquí.

Los archivos `.env` de cada computador se explican aparte, en
[Variables de entorno](VARIABLES_DE_ENTORNO.md).

Verificado el 2026-11-23 de dos formas: contra el código
(`infra/sagrilaft/lib/constructs/config-parameters.ts`, `secrets.ts` y
`sagrilaft-stack.ts`) y leyendo los parámetros reales de SSM en los dos ambientes.
Todos los valores de las tablas coinciden con lo que hay en AWS.

## Dos lugares para la configuración

- **Parameter Store (SSM):** valores que no son secretos, como direcciones web,
  tiempos de espera o el modelo de IA. Están en `/sagrilaft/<ambiente>/config/`.
- **Secrets Manager:** contraseñas y llaves, como las de la base de datos, el correo
  o Zoho. Se guardan cifradas y nunca se copian en documentos ni en git.

Los contenedores reciben ambos al arrancar. Si cambia un valor, hay que reiniciar
las tareas para que lo tomen (una release nueva lo hace).

**Quién escribe los parámetros:** CDK, desde `config-parameters.ts`. Para cambiar un
valor se cambia el código o el contexto de CDK y se despliega la infraestructura
([guía](../despliegue/GUIA_DESPLIEGUE_LOCAL.md#infraestructura)). Si se edita a mano
en la consola, el siguiente `cdk deploy` lo deja como estaba.

## Datos de la cuenta

| Dato | Valor |
|---|---|
| Cuenta AWS | `<CUENTA_AWS>` (compartida con otros proyectos: ver [etiquetado](ETIQUETADO_AWS.md)) |
| Región | `us-east-1` |
| Zona DNS | `ia.blend360.com` (`<HOSTED_ZONE_ID>`), compartida |
| Certificado | Comodín de ACM, compartido (`<ARN_CERTIFICADO_ACM>`) |

| Dominio | Staging | Producción |
|---|---|---|
| Formulario público (y la API en `/api`) | `forms-staging-sagrilaft.ia.blend360.com` | `forms-sagrilaft.ia.blend360.com` |
| Portal interno | `staging-sagrilaft.ia.blend360.com` | `sagrilaft.ia.blend360.com` |
| Inicio de sesión (Keycloak) | `login-staging-sagrilaft.ia.blend360.com` | `login-sagrilaft.ia.blend360.com` |

## Parámetros (SSM)

Cuando staging y producción usan el mismo valor, aparece una sola vez.

### Generales

| Parámetro | Para qué sirve | Staging | Producción |
|---|---|---|---|
| `APP_ENV` | Nombre del ambiente que ve la aplicación | `staging` | `production` |
| `AWS_REGION` | Región | `us-east-1` | igual |
| `FRONTEND_URL` | Orígenes web permitidos (CORS): formulario y portal | los dos dominios de staging | los dos dominios de producción |
| `PORTAL_INTERNO_URL` | Dirección del portal, para enlaces en correos | `https://staging-sagrilaft.ia.blend360.com` | `https://sagrilaft.ia.blend360.com` |
| `UVICORN_WORKERS` | Procesos del backend por copia | `4` | `4` |
| `TRUSTED_PROXY_IPS` | Red interna desde la que se acepta la IP real del visitante (la del balanceador). Ver [runbook](../../operacion/RUNBOOK_OPERATIVO.md#ip-real) | `10.0.0.0/16` (CDK lo toma de la red) | igual |
| `STORAGE_BACKEND` | Dónde se guardan los archivos | `s3` | igual |
| `S3_BUCKET` | Bucket de documentos | lo crea CDK | lo crea CDK |

### IA (Bedrock)

| Parámetro | Para qué sirve | Valor |
|---|---|---|
| `BEDROCK_MODEL_ID` | Modelo que lee los documentos | `amazon.nova-pro-v1:0` en los dos ambientes (decidido el 2026-10-20) |
| `BEDROCK_MAX_TOKENS` | Largo máximo de la respuesta | `4096` |
| `BEDROCK_TEMPERATURE` | Variación de la respuesta (0 = siempre igual) | `0.0` |
| `BEDROCK_CONNECT_TIMEOUT_SECONDS` / `BEDROCK_READ_TIMEOUT_SECONDS` | Tiempos de espera | `10` / `90` |
| `BEDROCK_MAX_ATTEMPTS` | Reintentos | `3` |
| `BEDROCK_PDF_MAX_PAGES` | Páginas de cada PDF que se envían a la IA | `7` |
| `BEDROCK_DEFAULT_CONFIDENCE` | Confianza que se asume si el modelo no la da | `0.90` |
| `BEDROCK_RESPONSE_LOG_CHARS` | Caracteres de la respuesta que se guardan en registros | `800` |

### Inicio de sesión (Keycloak)

| Parámetro | Valor |
|---|---|
| `KEYCLOAK_URL` | Dirección interna: `http://keycloak.sagrilaft-<ambiente>.local:8080` |
| `KEYCLOAK_REALM` / `KEYCLOAK_CLIENT_ID` | `sagrilaft` / `sagrilaft-portal` |
| `KEYCLOAK_ISSUER_URL` y `KEYCLOAK_HOSTNAME` | El dominio de inicio de sesión del ambiente |

### Correo y alertas

| Parámetro | Para qué sirve | Valor |
|---|---|---|
| `SMTP_HOST` / `SMTP_PORT` | Servidor de correo de AWS (SES) | `email-smtp.us-east-1.amazonaws.com` / `587` |
| `SMTP_FROM` y `SES_EMAIL_ORIGEN` | Remitente | `no-reply-sagrilaft@ia.blend360.com` |
| `SMTP_REPLY_TO` | A quién llegan las respuestas | `legal@blend360.com` |
| `SES_NOTIFICACIONES_ENABLED` | Avisos internos por correo | `true` |
| `ALERTAS_EMAIL_DESTINATARIO` | Quién recibe esos avisos; los mismos correos se suscriben a las alarmas | Se pasa al desplegar (`snsAlertasSub`). No se publica aquí; ver [destinatarios](#destinatarios) |
| `SNS_NOTIFICACIONES_ENABLED` | Envío de avisos de la aplicación por SNS. Apagado: las alarmas de CloudWatch usan SNS por su cuenta | `false` |

### Firma (Zoho Sign)

| Parámetro | Para qué sirve | Staging | Producción |
|---|---|---|---|
| `ZOHO_SIGN_TESTING` | Modo de pruebas de Zoho (no gasta créditos) | `true` | `false` |
| `ZOHO_REDIRECT_URI` | Dirección para obtener el permiso de Zoho | `https://<portal>/oauth/zoho/callback` | igual, con su dominio |
| `ZOHO_WEBHOOK_SIGNATURE_HEADER` | Cabecera con la firma de los avisos de Zoho | `X-ZS-WEBHOOK-SIGNATURE` | igual |
| `ZOHO_SIGN_REQUEST_EXPIRATION_DAYS` | Días que tiene la contraparte para firmar | `15` | igual |
| Tiempos y reintentos | `ZOHO_REFRESH_MARGIN_SECONDS` 300, `ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS` 3600, `ZOHO_HTTP_MAX_ATTEMPTS` 3, `ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS` 1.0, `ZOHO_HTTP_BACKOFF_FACTOR` 2, `ZOHO_TOKEN_TIMEOUT_SECONDS` 15, `ZOHO_STATUS_TIMEOUT_SECONDS` 15, `ZOHO_CANCEL_TIMEOUT_SECONDS` 15, `ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS` 30, `ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS` 30, `ZOHO_DOWNLOAD_TIMEOUT_SECONDS` 60 | | igual |

### Listas cautelares

| Parámetro | Para qué sirve | Staging | Producción |
|---|---|---|---|
| `PROVEEDOR_LISTAS_CAUTELA` | Cómo se consultan las listas | `dummy` (simulado) | `deshabilitado`: el código no permite otro valor en producción |
| `SAGRILAFT_API_URL` | Dirección del proveedor antiguo; sin uso con estos valores | `dummy://listas-cautela` | igual |
| `LISTAS_TUSDATOS_URL` | Dirección de Tusdatos (proveedor externo) | `https://dash-board.tusdatos.co` | igual |
| `LISTAS_CUSTODIA_BACKEND` / `LISTAS_CUSTODIA_S3_PREFIJO` | Dónde se guardan los informes de las consultas | `s3` / `listas/custodia/` | igual |

Activar el proveedor externo en producción requiere contrato, credenciales y un cambio
de código: ver [P15](../PENDIENTES_PRODUCCION.md#p15).

### Parámetro creado a mano

`/sagrilaft/prod/config/PORTAL_URL` vale `https://portal.sagrilaft.ia.blend360.com`, un
dominio que no es el del portal. No lo crea CDK ni lo lee el código (revisado el
2026-11-23). El 2026-11-03 se decidió conservarlo porque no se descartó que algo
externo lo use; esa decisión quedó en la versión anterior de
[Variables de entorno](VARIABLES_DE_ENTORNO.md) (historial de git). Está etiquetado como
`manual` ([etiquetado](ETIQUETADO_AWS.md)). Staging no lo tiene.

## Valores de los frontends (al construir las imágenes)

El formulario y el portal reciben estos valores al construir su imagen, no al
arrancar. El publicador de imágenes los toma de los parámetros del ambiente o usa
estos valores por defecto (`scripts/despliegue/build_and_push_ecr_images.py`).

| Valor | De dónde sale |
|---|---|
| `VITE_BACKEND_URL` | Vacío: el navegador llama a `/api` en el mismo dominio y el balanceador lo envía al backend |
| `VITE_PORTAL_INTERNO_URL` | `PORTAL_INTERNO_URL` |
| `VITE_KEYCLOAK_URL`, `VITE_KEYCLOAK_REALM`, `VITE_KEYCLOAK_CLIENT_ID` | Los parámetros de Keycloak |
| `VITE_RAZON_SOCIAL` / `VITE_CORREO_DATOS` | `HIGH TECH SOFTWARE S.A.S` / `administrativocol@blend360.com` (datos legales del formulario) |

## Secretos (Secrets Manager)

Todos se llaman `sagrilaft/<ambiente>/<nombre>`.

| Secreto | Campos | Quién lo escribe | Notas |
|---|---|---|---|
| `db_credentials` | `username`, `password` (la aplicación solo usa estos dos) | CDK lo genera | Llegan como `DB_USER`/`DB_PASSWORD` al backend y `KC_DB_USERNAME`/`KC_DB_PASSWORD` a Keycloak. En producción AWS agrega `host`, `port`, `dbname`, `engine` y `dbInstanceIdentifier`, que nadie lee |
| `app_secret` | `secret_key` | CDK lo genera | Llave con la que se sella (HMAC) el reporte PDF de auditoría |
| `keycloak_admin` | `username`, `password` | CDK lo genera | Usuario administrador de Keycloak (`username` es `admin`). No cambiarlo desde `.env`: se desincroniza con Keycloak |
| `zoho_credentials` | `client_id`, `client_secret`, `refresh_token`, `webhook_secret` | Se carga a mano (externo) | En producción CDK lo importa: desplegar siempre con `-c zohoSecretYaExiste=true` |
| `smtp_credentials` | `username`, `password` | Se carga a mano en la consola | Cada ambiente usa su propio usuario de SES (ver abajo) |
| `tusdatos_credentials` | `usuario`, `clave`, `token` | Se carga a mano cuando haya contrato | Hoy vacío en producción (verificado el 2026-11-23) |
| `sagrilaft_listas_cautela_credentials` | `api_key` | Se carga a mano | Llega al backend como `SAGRILAFT_API_KEY`; sin uso mientras las listas estén deshabilitadas |

**Correo (SMTP).** Staging y desarrollo local comparten el usuario IAM
`sagrilaft-ses-smtppp`; producción usa uno exclusivo, `ses-smtp-prod-sagrilaft`
(verificado el 2026-11-23: cada secreto usa la llave activa de su usuario). Hay
un tercer usuario, `sagrilaft-ses-smtpp`, sin uso confirmado: no se borra hasta
confirmarlo. Estas credenciales nunca van en `.env.staging` ni en `.env.prod`
(`scripts/validacion/validate_envs.py` lo rechaza).

**Zoho.** Staging y producción comparten la misma aplicación de Zoho (mismos
`client_id`, `client_secret` y `refresh_token`); solo `webhook_secret` cambia, porque
cada ambiente tiene su propio webhook (verificado el 2026-11-23 comparando huellas, sin
leer los valores). La idea original era tener dos aplicaciones
separadas; se dejó así porque funciona y no bloquea nada.

**Contraseña de la base de datos.** Cambiarla en Secrets Manager no la cambia en la
base. Hay que cambiar las dos en la misma ventana y comprobar la conexión. En staging
se cambió a mano el 2026-08-18 y el 2026-10-28 (por eso su secreto solo tiene dos
campos); producción conserva la generada por CDK.

**Cómo cargar un secreto externo** (Zoho o un proveedor de listas). El script no acepta
`--profile`: definir antes `AWS_PROFILE`.

1. Poner el valor en el archivo privado del ambiente (`.env.staging` o `.env.prod`).
   Si ese archivo está desactualizado, `--apply` sobrescribe el secreto correcto de AWS
   con el valor viejo: en octubre de 2026 `.env.prod` tenía la cuenta de Zoho anterior y
   hubo que corregirlo antes de sincronizar.
2. Ver qué haría, sin escribir nada:
   `python3 scripts/aws/sync_aws_runtime_assets.py --env-file .env.prod --environment prod --region us-east-1`
3. Revisar que solo aparezca el secreto esperado y ningún `ERROR`.
4. Escribir: el mismo comando con `--apply --expected-account <CUENTA_AWS>`.
5. Desplegar una release o reiniciar las tareas para que lo tomen.

El script nunca escribe los secretos que genera CDK. SMTP se carga en la consola.

Cuidados con los secretos que crea CDK:

- `smtp_credentials`, `sagrilaft_listas_cautela_credentials` y `tusdatos_credentials` se
  crean con un valor vacío fijo en el código y luego se llenan a mano. Si alguien cambia
  ese valor fijo en el código, el siguiente despliegue borra lo cargado.
- Ningún secreto tiene política de retención: si un recurso se elimina del stack, el
  secreto se borra con él.
- Si se cambia a mano en Keycloak la contraseña del administrador, hay que actualizar
  también `keycloak_admin`: Keycloak no la vuelve a leer del secreto.
Para comprobar si un secreto cambió, comparar la versión vigente (`AWSCURRENT`), no la
fecha de modificación: el etiquetado del 2026-11-18 cambió esa fecha en todos sin
tocar sus valores.

## Zoho Sign: aplicación y webhook

Zoho está en Estados Unidos (`accounts.zoho.com`, `sign.zoho.com`; la aplicación se
administra en `api-console.zoho.com`). El permiso que se pide es `ZohoSign.documents.ALL`:
el backend crea solicitudes, consulta su estado, las cancela y descarga los PDF firmados.
No usa plantillas de Zoho (`ZohoSign.templates.ALL` solo haría falta si se usaran).

| | Staging | Producción |
|---|---|---|
| Nombre del webhook en Zoho | `Sagrilaft-Staging` | `Sagrilaft-Produccion` |
| Dirección del webhook | `https://forms-staging-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign` | `https://forms-sagrilaft.ia.blend360.com/api/webhooks/zoho-sign` |

Configuración del webhook en Zoho:

- **Eventos marcados:** «Completados por todos», «Expira», «Retirado», «Rechazado» y «Duro rebotado».
- **Eventos apagados:** «Enviados», «Viendo», «Firmados por un destinatario», «Aprobados por un destinatario» y «Reasignados».
- **Seguridad:** firma HMAC SHA-256 en la cabecera `X-ZS-WEBHOOK-SIGNATURE`, con la clave
  `webhook_secret` del secreto. Sin Basic Auth ni mTLS.

Según el registro del 2026-10-20, los dos webhooks se recrearon ese día con firma HMAC;
eso se configura en la consola de Zoho y no se puede comprobar desde AWS. El de
producción no ha recibido ningún aviso (verificado en los registros del backend el
2026-11-23; ver [P05](../PENDIENTES_PRODUCCION.md#p05)).

<a id="destinatarios"></a>
## Destinatarios de alertas

La lista se pasa al desplegar como `snsAlertasSub` (correos separados por coma) y
queda en `ALERTAS_EMAIL_DESTINATARIO`. No se publica en el repositorio.

Desde el 2026-10-21 producción tiene un solo destinatario: un correo en SSM y una
suscripción confirmada en SNS (verificado el 2026-11-23). Staging también tiene uno. Los once destinatarios originales no se han vuelto a invitar; hacerlo
requiere autorización ([P06](../PENDIENTES_PRODUCCION.md#p06)). Para desplegar se lee
el valor vigente de SSM, para no cambiar la lista sin querer.

## Credenciales de AWS

Ningún ambiente usa llaves de acceso fijas (`AWS_ACCESS_KEY_ID`):

- **En AWS**, cada contenedor usa los permisos temporales de su rol.
- **En un computador**, se usa una sesión SSO:
  1. `aws sso login --profile PS-PowerUserAccess-<CUENTA_AWS>` (abre el navegador).
  2. En `.env`, `AWS_PROFILE=<ese perfil>`.
  3. Levantar el backend: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate backend`.
  4. Comprobar que el contenedor usa la sesión:
   `docker exec solucion-backend-1 python3 -c "import boto3; print(boto3.Session().get_credentials().method)"`
   debe imprimir `sso`.
5. La sesión caduca en unas horas; entonces se repite el paso 1.

## Lo que no debe llegar a AWS

Solo sirven en desarrollo local: `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `PORT_PUBLICO`, `PORT_PORTAL`, `PORTAL_AUTH_DISABLED` y
`KEYCLOAK_DB_URL`.
