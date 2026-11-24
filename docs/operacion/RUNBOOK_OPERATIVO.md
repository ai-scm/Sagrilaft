# Runbook de operación — SAGRILAFT

Qué revisar y qué hacer cuando algo falla. Las tareas abiertas están en
[Pendientes](../produccion/PENDIENTES_PRODUCCION.md) y el estado de cada ambiente, en
[Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md). Al final hay un
[historial](#historial) de simulacros e incidentes pasados, separado de los procedimientos.

Registros de cada servicio en CloudWatch: `/sagrilaft/<ambiente>/ecs/<servicio>`
(`backend`, `frontend`, `portal`, `keycloak`, `listas-worker`, `migration`).

<a id="alarmas"></a>
## 1. Alarmas

Las alarmas están en `infra/sagrilaft/lib/constructs/observabilidad-alarmas.ts`. Solo
mandan correo en producción; en staging existen pero no avisan, para no generar ruido
con los errores normales de las pruebas.

<a id="que-hacer-alarma"></a>
### Qué alarma llegó y qué hacer

Cada alarma manda un correo cuando algo falla y otro cuando se normaliza. El asunto
trae el nombre de la alarma y el cuerpo explica qué pasa.

| Alarma | Qué significa | Qué hacer |
|---|---|---|
| `AlarmaErroresServidor` | 5 o más errores del servidor en 5 minutos | Buscar `Traceback` en los registros del backend |
| `AlarmaSaturacionCpu` / `AlarmaSaturacionMemoria` | El backend usa más del 85 % de su CPU o memoria | El autoescalado agrega una copia (a partir del 60 % de CPU o el 70 % de memoria). Si sigue, revisar qué peticiones lo ocupan en los registros |
| `AlarmaSinCopiasSanas<servicio>` | El servicio (backend, formulario, portal o Keycloak) lleva 3 minutos sin ninguna copia funcionando. **Nadie puede usarlo.** Si es Keycloak, el equipo interno no puede iniciar sesión | En ECS, abrir el servicio y mirar la pestaña de eventos y los registros de la última tarea detenida. Si coincide con un despliegue, ver la [sección 4](#ecs) |
| `AlarmaCopiasNoSanas<servicio>` | Una copia lleva 5 minutos fallando su revisión de salud. Si hay otra sana, el servicio sigue con menos capacidad | Revisar los registros de esa copia. Si coincide con un despliegue, puede estar trabado |
| `AlarmaEspacioBaseDatos` | A la base le quedan menos de 10 GB libres (2 GB en staging). Si se llena, deja de guardar formularios | Ampliar el disco en RDS (no reinicia la base) y averiguar qué creció |
| `AlarmaCpuBaseDatos` | La CPU de la base lleva 15 minutos por encima del 80 % (lo normal es 4 %). Todo se vuelve lento | Revisar en RDS qué consulta la ocupa |
| `AlarmaConexionesBaseDatos` | 120 conexiones o más durante 10 minutos (lo normal son unas 10). Cerca de 190 empieza a rechazar nuevas | Ver si una copia del backend o de Keycloak quedó atascada y reiniciarla desde ECS |
| `AlarmaFirmaFallida` | Zoho Sign rechazó o no respondió al enviar, cancelar o descargar una firma | Lo más común: la cuenta se quedó sin créditos de API o cambiaron las credenciales. Ver la [sección 2](#zoho) |
| `AlarmaCorreoFallido` | No salió un correo a una contraparte (acceso, devolución, rechazo o reapertura). La contraparte no se enteró | Buscar `Error al enviar notificación` en los registros del backend para ver a quién y por qué. Revisar SES y reenviar desde el portal si hace falta |

Las dos últimas salen de filtros sobre los registros del backend: la de firma cuenta las
respuestas 502 (el backend solo responde 502 cuando falla Zoho) y la de correo cuenta
las líneas «Error al enviar notificaci» (sin la tilde final, porque los textos que van a
AWS no llevan tildes). Si algún día el backend usa 502 para otra cosa, hay que ajustar
el filtro.

Al desplegar una alarma nueva llega un correo «OK»: es CloudWatch confirmando que la
alarma arrancó bien.

### Si no llegan los avisos

1. En CloudWatch, mirar el estado y el historial de la alarma.
2. Comprobar que el tema SNS de producción tenga las suscripciones esperadas en estado
   confirmado (no `PendingConfirmation`).
3. Comprobar que `ALERTAS_EMAIL_DESTINATARIO` en SSM coincida con la lista vigente.
4. Revisar los resultados de entrega de SNS.

Para probar de verdad una alarma ([P06](../produccion/PENDIENTES_PRODUCCION.md#p06)) hay
que provocar una métrica real que cruce el umbral. Forzar el estado con `SetAlarmState`
solo prueba el envío, no la evaluación de la métrica.

<a id="zoho"></a>
## 2. Firma electrónica (Zoho Sign)

<a id="reintentos"></a>
### Error al enviar a firma

El backend llama a Zoho en dos pasos (crear el borrador y enviarlo) y reintenta hasta
3 veces, con esperas de 1 y 2 segundos, ante respuestas 429, 502, 503, 504 o fallas de
red. Si no lo logra, responde 502 con un campo `hint`:

- **«Falla temporal del proveedor de firma electrónica. Reintente en unos minutos.»**
  Esperar 2 o 3 minutos y volver a pulsar «Enviar a firma». Es seguro reintentar.
- **«Problema de credenciales con el proveedor de firma electrónica…»** No sirve
  reintentar. Revisar en la consola de Zoho que el `refresh_token` siga vigente y que la
  cuenta tenga créditos de API. Las credenciales están en
  `sagrilaft/<ambiente>/zoho_credentials`.

En los registros del backend: `Resiliencia API: Falla transitoria` (se agotaron los
reintentos) o la traza de `ZohoSignAutenticacionError` / `ZohoSignIndisponibleError`,
con el código HTTP que devolvió Zoho.

Qué pasa con el expediente si falla:

- **Sigue en `VALIDADO`.** Solo pasa a `PENDIENTE_FIRMA` cuando Zoho responde bien.
- **El certificado SAGRILAFT no se duplica.** Se genera antes de llamar a Zoho y, en el
  siguiente intento, se actualiza el mismo.

Las pruebas que cubren esto están en `tests/integration/test_expediente_firma.py` y
`tests/unit/test_zoho_sign_service_reintentos.py`.

<a id="huerfanos"></a>
### Borradores huérfanos

Si Zoho crea el borrador pero el envío falla, el sistema no guarda el `request_id` y el
borrador queda en Zoho sin forma de cancelarlo desde el portal. No es grave: Zoho no
cobra un borrador que nunca se envió y el firmante no recibe nada. Corregirlo está en
[P16](../produccion/PENDIENTES_PRODUCCION.md#p16).

### La firma se completó pero el expediente no cambia

El webhook de Zoho llega a `POST /api/webhooks/zoho-sign` y se valida con la firma HMAC
de la cabecera `X-ZS-WEBHOOK-SIGNATURE` y el `webhook_secret` del ambiente
([configuración del webhook](../produccion/configuracion/MATRIZ_AWS_CONFIG.md#zoho-sign-aplicación-y-webhook)).

1. Buscar en los registros del backend `WEBHOOK_TOKEN_INVALID`. Si aparece, el
   `webhook_secret` de AWS no coincide con el configurado en Zoho, o el webhook se borró
   en Zoho.
2. Si no llega ninguna petición, revisar en la consola de Zoho que el webhook exista y
   apunte al dominio del formulario del ambiente.
3. Mientras tanto, el botón «Verificar estado» del portal consulta a Zoho y actualiza el
   expediente a mano.

Un webhook repetido no hace daño: si el expediente ya está `FIRMADO`, se ignora.

## 3. Errores al subir documentos

Si en los registros del backend aparece `botocore.errorfactory.NoSuchKey` con
`GetObject` al subir un documento, es el patrón de dos subidas simultáneas del mismo
archivo. Se corrigió en septiembre de 2026 (cada subida tiene su propia clave en S3), así
que si vuelve a aparecer es una regresión: revisar `key_borrador()` en
`backend/services/formulario/documento_service.py`.

Si la contraparte ve «Demasiadas solicitudes», es el límite de 60 subidas por minuto
(ver [IP real](#ip-real) si le pasa a mucha gente a la vez).

<a id="ecs"></a>
## 4. Un despliegue no termina o se revierte

Cuando las tareas nuevas no quedan sanas, ECS cancela el despliegue y CloudFormation
vuelve a la versión anterior (circuit breaker).

1. `aws cloudformation describe-stack-events --stack-name SagrilaftStack-<ambiente>` y
   buscar `ECS Deployment Circuit Breaker was triggered` para ver qué servicio falló.
2. Ver los registros de ese servicio en el momento del fallo.
   - `CannotPullContainerError`: falta la imagen con ese tag en ECR. Las cuatro imágenes
     tienen que existir con el mismo SHA ([guía](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md#build)).
   - El contenedor respondía `200` al revisor de salud del balanceador
     (`ELB-HealthChecker/2.0`) y aun así lo detuvieron: el tiempo de gracia es corto.
     Comparar con `aws ecs describe-services --query "services[0].healthCheckGracePeriodSeconds"`.
     Hoy es de 180 s en el backend y 300 s en formulario, portal y Keycloak.

**No interrumpir un `cdk deploy` en curso.** Cortarlo con Ctrl+C fuerza una reversión
que puede tardar más y dejar el stack en `UPDATE_ROLLBACK_FAILED`. Si eso pasa:
`aws cloudformation continue-update-rollback --stack-name SagrilaftStack-<ambiente>`.
Un despliegue completo puede tardar de 10 a 15 minutos.

<a id="despliegue-coordinado"></a>
## 5. Falló una release con `deploy_release.py`

El script deja un lock en el bucket del stack (`_deployment/<stack>.lock`). Si algo
falla, se agota el tiempo o se interrumpe, el lock **se queda puesto** a propósito: no
vence solo ni se libera por reintentar.

Antes de decidir qué hacer:

1. Guardar el plan, `events.jsonl`, el ARN y el resultado de la tarea de migración, los
   digests, la evidencia de Alembic y el estado de CloudFormation y ECS.
2. Averiguar si la migración terminó y en qué revisión quedó la base.
3. No borrar el lock ni relanzar la migración solo porque pasó tiempo. Liberarlo
   requiere revisar el caso y una autorización para esa acción concreta.

Volver atrás tiene límites:

- La reversión de ECS o CloudFormation no deshace la migración de la base ni recupera
  datos.
- Volver a una imagen anterior solo sirve si esa versión funciona con el esquema actual.
  No se reconstruye la imagen ni se ejecuta `alembic downgrade` automáticamente.
- Si la versión anterior no es compatible, hay que corregir hacia adelante o restaurar
  la base ([sección 6](#restauracion)).

En staging, con validación manual, la salida con código **3** (`manual_validation_pending`)
no es un fallo: los servicios ya están activos y falta que el operador complete la
validación ([guía](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md#smoke-manual)). No
relanzar el despliegue. Si el cierre se interrumpe después de pedir el borrado del lock,
comprobar en S3 si el lock sigue antes de reintentar.

<a id="restauracion"></a>
## 6. Respaldos y restauración de la base

### Qué copias hay

- **Automáticas:** 14 días en producción y 7 en staging
  ([database.ts](../../infra/sagrilaft/lib/constructs/database.ts)). RDS las borra solo al
  vencer; no se borran a mano.
- **Antes de cada despliegue con migración:** una copia manual. Se borra cuando el
  siguiente despliegue con migración esté verificado. No debería haber más de una o dos
  de este tipo.
- **Antes de abrir a usuarios:** limpiar los datos de prueba ([P21](../produccion/PENDIENTES_PRODUCCION.md#p21)),
  tomar `sagrilaft-prod-pre-salida-produccion-<AAAAMMDD>` y conservarla de 30 a 90 días.
- **Staging:** sin copias manuales; no tiene datos que importen.
- Cuando haya datos reales, confirmar con Cumplimiento cuánto tiempo hay que conservar la
  información antes de definir cualquier purga.

Copias manuales de producción hoy:

- `sagrilaft-prod-base-pre-pruebas-20261123`: se tomó **después** de las pruebas hechas
  en producción, así que contiene esos datos ([P21](../produccion/PENDIENTES_PRODUCCION.md#p21)).
  No sirve como base limpia. Se borra cuando exista la copia de salida a producción.
- `sagrilaft-prod-pre-ip-cliente-20261123`: tomada antes del despliegue del 2026-11-23.

Una copia manual lleva las cuatro etiquetas y `ManagedBy=manual`, para no confundirla
con las automáticas ([comando](../produccion/configuracion/ETIQUETADO_AWS.md#snapshots-de-rds)).
La cuenta tiene bases de otros proyectos: filtrar siempre por `sagrilaftstack-<ambiente>-`.

### Restaurar

Nunca se restaura sobre la base original: siempre en una instancia nueva, que se borra
al terminar. La base no tiene salida a internet, así que la revisión se hace desde dentro
de la VPC con una tarea de ECS.

1. Elegir la copia:

   ```bash
   aws rds describe-db-snapshots --db-instance-identifier <INSTANCIA> \
     --query "DBSnapshots[].[DBSnapshotIdentifier,SnapshotCreateTime]" --output table
   ```

2. Restaurar en una instancia nueva, con el mismo grupo de subredes y el mismo grupo de
   seguridad de la original (ya permite el puerto 5432 desde ECS):

   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier sagrilaft-<ambiente>-restore-<fecha> \
     --db-snapshot-identifier <copia> \
     --db-instance-class <clase> \
     --db-subnet-group-name <grupo-de-subredes> \
     --vpc-security-group-ids <sg-de-rds> \
     --no-multi-az --no-publicly-accessible
   aws rds wait db-instance-available --db-instance-identifier sagrilaft-<ambiente>-restore-<fecha>
   ```

3. Revisar los datos con una tarea puntual de la definición de migración
   (`sagrilaft-<ambiente>-migration`, contenedor `migration`), cambiando `DATABASE_HOST`
   por el endpoint restaurado y el comando por una consulta de solo lectura (revisión de
   Alembic y conteo de tablas clave). No ejecutar migraciones contra la copia.

   ```bash
   aws ecs run-task --cluster sagrilaft-<ambiente> --launch-type FARGATE \
     --task-definition <arn-de-la-definicion-de-migracion> \
     --network-configuration "awsvpcConfiguration={subnets=[<subredes-privadas>],securityGroups=[<sg-de-ecs>],assignPublicIp=DISABLED}" \
     --overrides '{"containerOverrides":[{"name":"migration","environment":[{"name":"DATABASE_HOST","value":"<endpoint-restaurado>"}],"command":["sh","-c","<consulta>"]}]}'
   ```

4. Borrar la instancia temporal:
   `aws rds delete-db-instance --db-instance-identifier sagrilaft-<ambiente>-restore-<fecha> --skip-final-snapshot`.

En staging tardó de 10 a 15 minutos hasta quedar disponible (simulacro del 2026-09-19).
En producción no se ha ensayado ([P10](../produccion/PENDIENTES_PRODUCCION.md#p10)).
Keycloak usa la misma base: restaurar también devuelve usuarios y sesiones al momento de
la copia.

<a id="ip-real"></a>
## 7. Desde qué IP se hizo una petición

Hay dos fuentes:

- **Registros de la aplicación** (`/sagrilaft/<ambiente>/ecs/backend`). Los avisos de
  seguridad (`RATE_LIMIT_EXCEEDED`, `CREDENTIALS_INVALID`, `ACCESS_DENIED`,
  `AUTH_FAILED`) traen `ip=` con la IP real del visitante. Si en cambio aparece una
  dirección `10.0.x.x`, el backend no está leyendo la IP real: revisar que
  `TRUSTED_PROXY_IPS` sea la red de la VPC. Las líneas de acceso del servidor web
  (`INFO:     10.0.x.x:puerto - "POST /api/..."`) siempre muestran la IP del
  balanceador; eso es normal.
- **Registros de acceso del balanceador** (bucket `Lb/RegistrosAcceso` del stack,
  carpeta `alb/`). Guardan cada petición con fecha, IP real, dirección pedida y
  respuesta. Llegan cada 5 minutos y se borran solos a los 90 días. Sirven aunque la
  aplicación haya fallado.

Si alguien ve «Demasiadas solicitudes. Intente más tarde.», es el límite de intentos por
persona: esperar un minuto y repetir. Si le pasa a mucha gente a la vez y todos los
avisos traen la misma IP `10.0.x.x`, se perdió la IP real.

<a id="ses"></a>
## 8. Correo

Los correos salen por SES desde `no-reply-sagrilaft@ia.blend360.com`, con respuesta a
`legal@blend360.com`. El dominio `ia.blend360.com` está verificado en SES con DKIM; la
identidad se creó fuera de este proyecto y CDK solo la importa.

**Outlook y Hotmail pueden mandar los correos a spam.** Gmail y Yahoo los entregan en la
bandeja y SPF, DKIM y DMARC pasan, así que no es un problema de configuración sino de
reputación del remitente ante Microsoft. Se reportó a Microsoft en septiembre de 2026,
sin respuesta. El riesgo está aceptado ([P02](../produccion/despliegue/P02_GO_NO_GO_ROLLBACK.md#riesgo-outlook));
hay que revisar los primeros envíos de producción.

Si una contraparte no recibe el correo:

1. Pedirle que revise spam, sobre todo si usa Outlook o Hotmail.
2. Buscar `Error al enviar notificación` en los registros del backend.
3. Revisar el estado de la cuenta con `aws sesv2 get-account` (debe decir
   `ProductionAccessEnabled: true` y `EnforcementStatus: HEALTHY`).
4. Reenviar las credenciales desde el portal (una vez cada 2 minutos como máximo).

<a id="herramientas"></a>
## 9. Problemas conocidos de las herramientas

- **AWS CLI del sistema con Python 3.14:** algunos comandos, como `aws sns publish`,
  fallan con `ValueError: badly formed help string`. Hacer la misma llamada con `boto3`
  desde `venv/bin/python`.
- **Cortes de DNS al publicar o desplegar:** `docker push` y `cdk deploy` a veces fallan
  con `i/o timeout` o `EAI_AGAIN`. Reintentar el mismo comando.
- **Procesos largos:** para algo que dura muchos minutos (una prueba de carga, por
  ejemplo), lanzarlo con `nohup … > log 2>&1 < /dev/null &` para que siga aunque se cierre
  la sesión.

<a id="historial"></a>
## Historial de simulacros e incidentes

Resultados pasados. No describen el estado actual; el detalle completo de cada uno está
en el historial de git de este archivo.

| Fecha | Qué pasó | Resultado |
|---|---|---|
| 2026-09-19 | Simulacro de restauración de RDS en staging | Restaurada en 10 a 15 min, datos completos, instancia temporal borrada |
| 2026-09-19 | Envío de prueba SNS → correo en staging | Correo recibido |
| 2026-09-21 | Despliegues de staging revertidos por el circuit breaker | Formulario y portal no tenían tiempo de gracia. Se fijó 180 s en el backend y 300 s en los demás (commit `7760859` y siguiente) |
| 2026-09-21/22 | Prueba de carga contra la subida de documentos (hasta 20 usuarios simultáneos) | Primero 1.355 de 1.403 peticiones fallaron por dos subidas con la misma clave en S3. Tras el arreglo (`164d7fe`): 0 errores en 2.207 peticiones, p95 de 3,3 s, CPU máxima del 47,6 %. El autoescalado no actuó porque el límite por IP frenó el tráfico ([P09](../produccion/PENDIENTES_PRODUCCION.md#p09)) |
| 2026-09-22 | Errores de Zoho llegaban como un 500 genérico | Ahora responden 502 con una pista de qué hacer ([sección 2](#reintentos)) |
| 2026-09-23 | Salida de SES del sandbox y cambio de remitente al dominio `ia.blend360.com` | Gmail y Yahoo a bandeja de entrada; Outlook a spam ([sección 8](#ses)) |
| 2026-09-24 | Primera firma real con la cuenta oficial de Zoho en staging | Se encontraron y corrigieron dos errores del webhook: la firma HMAC en base64 se recortaba (`tests/unit/test_webhooks_hmac.py`) y el estado `completed` llegaba en minúscula (`tests/unit/test_webhook_status_casing.py`) |
| 2026-10-07 | Prueba de la alarma 5xx de producción forzando su estado | Llegaron los correos de alarma y de recuperación |
| 2026-10-20 | Los webhooks de Zoho se habían borrado; se recrearon. Firma real en staging (`SAG-9C58BEF6`) | El webhook pasó el expediente a `FIRMADO`. Se corrigió que el portal no mostraba la firma sin recargar (release `767b3ac`) |
| 2026-10-21 | Primer corte de producción: el cliente de `cdk deploy` falló por red (`ECONNRESET`) después de que CloudFormation terminara | Producción quedó sana (verificación manual 12/12); el lock se liberó el 2026-10-24 ([evidencia](../evidencia/primer-corte-prod-20261021/README.md)) |
| 2026-11-03 | Primer intento de firma en producción | Zoho lo rechazó por falta de créditos de API ([P05](../produccion/PENDIENTES_PRODUCCION.md#p05)) |

Lección que sigue valiendo: los dos errores del webhook pasaron las pruebas porque las
pruebas usaban el mismo formato que esperaba el código, no el que manda Zoho. Toda
integración externa nueva debe probarse al menos una vez contra el proveedor real.
