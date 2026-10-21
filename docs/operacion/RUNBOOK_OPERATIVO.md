# Runbook Operativo — SAGRILAFT

Función única: procedimientos de diagnóstico/recuperación y registros históricos
de sus simulacros e incidentes. Las acciones abiertas se gestionan exclusivamente
en el [registro de tareas](../produccion/PENDIENTES_PRODUCCION.md); los resultados
históricos de este archivo no acreditan el estado actual del ambiente.

Estado de simulacros:

| Simulacro | Estado | Fecha |
|---|---|---|
| SNS → correo (staging + acción de alarma productiva controlada; umbral métrico real pendiente) | Parcial | 2026-09-19 / 2026-10-07 |
| Restauración de backup RDS | Hecho | 2026-09-19 |
| Prueba de carga (autoscaling + timeout Bedrock) | Hecho (v1 + v2 tras fix) | 2026-09-21/22 |
| Fix de concurrencia en subida de documentos | Hecho, validado bajo carga real | 2026-09-22 |
| Fix de `healthCheckGracePeriod` (Circuit Breaker en deploys) | Hecho, deploy exitoso | 2026-09-21 |
| Sección 2 — Reintentos de Zoho Sign agotados | Hecho, spec + implementación + tests | 2026-09-22 |
| Sección 8 — Salida de sandbox SES y entregabilidad | Hecho (deploy + pruebas), Outlook en gestión con Microsoft | 2026-09-23 |

---

<a id="alarmas"></a>
## 1. Notificaciones (SNS → correo) no llegan

### Contexto y limitación conocida

Las 3 alarmas críticas de CloudWatch (`AlarmaErroresServidor` ≥5 5xx/5min,
`AlarmaSaturacionCpu` ≥85%, `AlarmaSaturacionMemoria` ≥85%, definidas en
`infra/sagrilaft/lib/constructs/observabilidad-alarmas.ts`) **solo despachan
al topic SNS cuando `ambiente === 'prod'`**. Es una decisión deliberada del
código para no generar ruido en staging (ver comentario en el mismo archivo:
"Esto evita fatiga de alarmas en Staging donde es normal que los
desarrolladores causen errores 500").

Producción ya tiene el topic y las alarmas. El 2026-10-07 se probó de forma
controlada la acción de la alarma 5xx con `SetAlarmState`: CloudWatch invocó
SNS al pasar a `ALARM` y al volver a `OK`, y el operador confirmó ambos
correos. Esta prueba valida la acción configurada y su entrega, pero no la
evaluación de un umbral a partir de métricas reales. La evidencia está en
`docs/evidencia/sns-prueba-temporal-prod-20261007.json`.

### Simulacro ejecutado — SNS → correo (2026-09-19)

1. Topic identificado: `<ARN_TOPIC_SNS>`
   (cuenta `<CUENTA_AWS>`, región `us-east-1`).
2. Suscripción confirmada: protocolo `email`, endpoint
   `<correo-interno>` (destinatario único configurado para staging).
3. Publicación de prueba vía `boto3` (se evitó el AWS CLI del sistema por un
   bug conocido: Python 3.14 rompe el parseo de ayuda de `aws sns publish`
   con `ValueError: badly formed help string` — ver sección 7):

   ```python
   import boto3
   session = boto3.Session(profile_name="PS-PowerUserAccess-<CUENTA_AWS>", region_name="us-east-1")
   sns = session.client("sns")
   sns.publish(
       TopicArn="<ARN_TOPIC_SNS>",
       Subject="[SIMULACRO Runbook] Prueba de notificacion SNS - 2026-09-19",
       Message="...",
   )
   ```

4. Resultado: `MessageId: 3a234ac7-af37-5271-836e-29eef455650b`, correo
   recibido y confirmado por el destinatario el mismo día.

### Procedimiento de verificación productiva — [P06](../produccion/PENDIENTES_PRODUCCION.md#p06)

- La prueba controlada de `SetAlarmState` valida la transición de estado y la
  acción SNS; no acredita que una métrica real cruce el umbral. Durante la
  prueba solo estuvo confirmada la suscripción temporal, que ya se retiró;
  ninguna de las once definitivas recibió los mensajes.
- Estado al 2026-10-21: la suscripción de `Bryan.Ariza@blend360.com` está
  confirmada. Las once originales no existen en SNS aunque CloudFormation las
  conserve (drift); no se les ha enviado invitación. Decisión del mismo día:
  la lista efectiva es solo ese correo hasta autorizar a los otros once
  (alineación pendiente de despliegue). Ver
  [evidencia del 2026-10-21](../evidencia/sns-alertas-prod-20261021/README.md).
- Para cerrar P06, con las suscripciones autorizadas confirmadas y los
  servicios activos, provocar una condición métrica aprobada que cruce un
  umbral real y verificar que el aviso llegue a la lista definitiva en menos
  de cinco minutos. No usar `SetAlarmState` como sustituto de esa validación.
- Si no llega: revisar (a) el estado e historial de la alarma en CloudWatch,
  (b) que el topic de prod tenga las suscripciones esperadas confirmadas (no
  `PendingConfirmation`), (c) que `ALERTAS_EMAIL_DESTINATARIO` en SSM coincida
  con la lista vigente y (d) los resultados de entrega de SNS.

---

<a id="reintentos"></a>
## 2. Reintentos de Zoho Sign agotados

### Contexto

`enviar_a_firma()` (`firma_service.py`) llama a Zoho en dos pasos internos
(crear borrador + submit) a través de `ZohoSignService`, que reintenta hasta
3 veces con backoff exponencial (1s, 2s) ante `429/502/503/504` o fallas de
red. Si los reintentos se agotan, o si Zoho responde `401/403`
(autenticación), la llamada falla — hasta el 2026-09-22 esto llegaba al
operador como un **500 genérico**, indistinguible de cualquier otro error
inesperado.

### Fix implementado (2026-09-22)

`ZohoSignService` ahora traduce el fallo al tipo de dominio correcto:
- **Error transitorio agotado** (5xx/429/red, tras los 3 intentos) →
  `ZohoSignIndisponibleError` → HTTP **502**, hint: *"Falla temporal del
  proveedor de firma electrónica. Reintente en unos minutos."*
- **Error de autenticación** (401/403 en refresco de token, creación o
  submit) → `ZohoSignAutenticacionError` → HTTP **502**, hint: *"Problema de
  credenciales con el proveedor de firma electrónica. Escale a
  soporte/administración de credenciales de ZohoSign."*

La política de reintentos (3 intentos, backoff 1s/2s, códigos reintentables
429/502/503/504) **no cambió** — solo se tradujo la excepción final.

### Diagnóstico para el operador/soporte

1. **Mirar el campo `hint` de la respuesta** del endpoint
   `POST /api/expedientes/{formulario_id}/enviar-a-firma` — ya indica
   directamente si reintentar o escalar.
2. Si el `hint` dice "reintente en unos minutos": esperar 2-3 minutos y volver
   a pulsar "Enviar a firma" en el portal. Es seguro — ver invariantes abajo.
3. Si el `hint` dice "escale a soporte/credenciales": no tiene sentido
   reintentar de inmediato — escalar a quien administra las credenciales de
   ZohoSign (`ZOHO_CLIENT_ID`/`ZOHO_CLIENT_SECRET`/`ZOHO_REFRESH_TOKEN` en
   Secrets Manager) para confirmar que el `refresh_token` no fue revocado.
4. En logs del backend, buscar `Resiliencia API: Falla transitoria` (agotó
   reintentos) o el traceback de `ZohoSignAutenticacionError`/
   `ZohoSignIndisponibleError` para el detalle exacto (incluye el HTTP status
   de Zoho).

### Estado del formulario y del certificado ante una falla (invariantes verificados)

- **El formulario permanece en `VALIDADO`** — el cambio a `PENDIENTE_FIRMA`
  solo se comitea a BD *después* de que Zoho responde con éxito. Es seguro
  reintentar desde el botón sin riesgo de dejarlo en un estado intermedio
  roto.
- **El certificado SAGRILAFT no se duplica al reintentar** — se genera y
  comitea a BD *antes* de llamar a Zoho (para tenerlo listo para el paquete);
  si el intento anterior falló, ya existe uno, y `_registrar_certificado` lo
  **actualiza in-place** en el siguiente intento en vez de crear otro.
- Ambos invariantes están cubiertos por tests de integración
  (`tests/integration/test_expediente_firma.py`):
  `test_falla_transitoria_de_zoho_responde_502_y_formulario_sigue_validado`,
  `test_falla_autenticacion_de_zoho_responde_502_con_hint_de_escalar`,
  `test_reintento_exitoso_tras_falla_no_duplica_certificado`. Cobertura
  unitaria de la traducción de excepciones en
  `tests/unit/test_zoho_sign_service_reintentos.py`.

<a id="huerfanos"></a>
### Limitación conocida (registro histórico)

Si el **Paso 1** (crear borrador en Zoho) tiene éxito pero el **Paso 2**
(submit) falla, el `request_id` de ese borrador nunca se devuelve ni se
persiste en nuestra BD — queda un borrador huérfano en Zoho, sin referencia
en nuestro sistema y sin forma de cancelarlo desde el portal. No es
destructivo: Zoho no cobra crédito por un borrador que nunca se envió
(`submit`), y el firmante no recibe ningún correo de ese intento fallido. Se
documenta como limitación conocida de higiene de datos, no como error
crítico — corregirlo requeriría capturar la falla del Paso 2 dentro de
`crear_solicitud_firma_multiple` para invocar `cancelar_solicitud_firma` con
el `request_id` del Paso 1, lo cual queda fuera del alcance de este fix.

<a id="carga"></a>
## 3. Fallos de IA / Bedrock (timeout, cuota 429)

### Simulacro ejecutado (2026-09-21)

Carga real contra `POST /api/formularios/{formulario_id}/documentos` (dispara
una llamada a Bedrock por carga), en escalones de 3→6→10 VUs concurrentes
durante 10 minutos, sobre un formulario real de staging
(`SAG-611F4FB3`, `formulario_id=37b4b578-d1b1-4460-b962-766bb193b6ad`).

- Baseline sin carga: **~3.4s** por extracción exitosa.
- Bajo carga (peticiones que llegaron a ejecutarse): latencias entre 2.0s y
  3.6s — sin degradación relevante, sin acercarse al timeout de 300s del ALB.
- **0 timeouts** observados.
- Ningún request se acercó al límite de 300s en esta prueba — con la
  concurrencia probada (máx. 10 VUs), Bedrock nunca fue el cuello de botella.

### Repetición tras el fix de concurrencia (2026-09-22, v2)

Con el fix de `key_borrador()` (sección "Hallazgo real de concurrencia" abajo)
ya desplegado en staging, se repitió la prueba con escalones más altos
(5→10→15→20 VUs concurrentes, ~14 minutos, mismo formulario real
`SAG-611F4FB3`):

| Métrica | v1 (con el bug) | v2 (con el fix) |
|---|---|---|
| Total requests | 1403 | 2207 |
| `200 OK` | 48 | **1814** |
| `500` | 1355 | **0** |
| `429` (rate limit) | 0 | 393 |
| Latencia (con carga) | 2.0-3.6s | p50=2.35s / p95=3.34s / max=5.87s |

**0 errores 500 y 0 timeouts** en 2207 requests — el fix de concurrencia
queda validado bajo carga real concurrente, no solo en tests unitarios/de
integración. Bedrock y el timeout de 300s del ALB siguen sin ser un problema
incluso con el volumen real (1814 extracciones reales) que esta vez sí llegó
al backend.

Los 393 `429` son el rate limiter (`60/minute` en `subir_documento`)
funcionando como se espera — no un fallo. Confirma que, desde una sola IP,
existe un techo real de tráfico antes de generar más presión de CPU (ver
sección 4).

### Hallazgo real de concurrencia (no es un problema de Bedrock/timeout)

De 1403 requests disparados durante los 10 minutos, solo 48 terminaron en
`200`; **1355 terminaron en `500`**. La causa, confirmada en los logs de
CloudWatch (`/sagrilaft/staging/ecs/backend`), es un error real de
concurrencia, no un problema de capacidad ni de Bedrock:

```
botocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling
the GetObject operation: The specified key does not exist.
```

**Causa raíz:** `DocumentoService.key_borrador()` construye la key de S3 solo
a partir de `codigo_peticion` + `nombre_archivo` (`tmp/{codigo_peticion}/{nombre}`),
sin incluir `tipo_documento` ni un identificador único por carga. Cuando dos
subidas casi simultáneas usan el mismo nombre de archivo para el mismo
formulario:

1. La subida A escribe el contenido en la key `tmp/<codigo>/<archivo>.pdf`.
2. `reemplazar_documento_anterior()` (con bloqueo `FOR UPDATE` a nivel de
   fila en BD, pero **sin protección a nivel de archivo en S3**) encuentra el
   documento anterior con esa misma key y lo elimina de S3.
3. Otra subida B, todavía en curso, intenta leer esa key para mandarla a
   Bedrock (`analisis_service.py:173`) — y el archivo ya no existe.

**Cómo se dispara en producción real** (no requiere doble-click exacto ni
alta concurrencia sintética): un usuario que reintenta subir el mismo archivo
por lentitud de red, o dos pestañas/sesiones del mismo formulario, generan
el mismo patrón. El bloqueo de base de datos protege la fila del registro,
no el archivo físico en S3 — por eso la carga concurrente lo destapó.

**Diagnóstico rápido si aparece en producción:**
- Buscar en logs del backend `botocore.errorfactory.NoSuchKey` con
  `GetObject` — confirma este patrón específico.
- Revisar si el usuario reportó un reintento de subida o múltiples pestañas
  abiertas para el mismo acceso.
- Ver `documentos_adjuntos` en BD: debería existir un registro de versión
  posterior (`version_numero` incrementado) que sí tiene su archivo íntegro
  en S3 — el fallo es transitorio para el intento perdedor de la carrera, no
  corrompe el documento final.

**Fix implementado y desplegado (2026-09-21/22):** `key_borrador()` ahora
incluye un identificador único de 12 caracteres hex (`uuid.uuid4().hex[:12]`)
en la key, además del nombre de archivo sanitizado
(`tmp/{codigo_peticion}/{identificador_unico}_{nombre_archivo}`). Cada carga
obtiene su propia key física en S3, sin importar si coincide el nombre de
archivo. Cambios:
- `backend/services/formulario/documento_service.py` — la función.
- `tests/unit/test_documento_service_key_borrador.py` — test nuevo que prueba
  la unicidad de la key directamente (regresión de la causa raíz).
- `tests/integration/test_documentos_adjuntos.py` — assertions de ruta exacta
  actualizadas a patrones (la key ya no es determinística), más un test nuevo
  `test_subidas_concurrentes_con_mismo_nombre_archivo_no_generan_500` que
  reproduce 8 subidas HTTP concurrentes reales contra el mismo formulario y
  nombre de archivo (verificado que sin el fix, este test falla — con el fix,
  pasa). Suite completa: 89 passed, 1 skipped.
- Commit `164d7fe` (fix + tests). Validado bajo carga real en staging el
  2026-09-22 (ver "Repetición tras el fix" arriba): 0 errores 500 en 2207
  requests, contra 1355/1403 antes del fix.

<a id="autoscaling"></a>
## 4. CPU/memoria saturada — autoscaling vs. intervención manual

### Simulacro ejecutado (2026-09-21)

Con el mismo escalón de carga (3→6→10 VUs concurrentes, 10 minutos), medido
con `aws cloudwatch get-metric-statistics` sobre `AWS/ECS CPUUtilization` del
servicio backend:

- CPU máxima observada: **26.6%** (ventana `00:53:00Z`), muy por debajo del
  umbral de autoscaling (60%).
- `desiredCount`/`runningCount` se mantuvieron estables en **2/2** durante
  todo el simulacro — el autoscaling **no se activó**, porque no hizo falta.

**Interpretación:** con la carga sintética generada (máx. 10 VUs, con el bug
de concurrencia de la sección 3 limitando a ~48 peticiones exitosas de 1403
intentadas), el backend nunca estuvo cerca de estresarse. Este resultado no
valida el comportamiento del autoscaling en un pico real — solo confirma que,
para el volumen probado, la capacidad base (2 tareas) es suficiente.

### Repetición tras el fix (2026-09-22, v2) — resultado final aceptado

Con el bug de concurrencia corregido y desplegado, y escalones más altos
(5→10→15→20 VUs), el backend generó 1814 extracciones reales contra Bedrock
(vs. 48 antes). CPU real medido con `aws cloudwatch get-metric-statistics`:

| Ventana | CPU promedio | CPU máximo |
|---|---|---|
| 5 VUs | 9.8-13.4% | ~19% |
| 10 VUs | 18.1-23.2% | ~28% |
| 15 VUs | 23.8-29.7% | ~38.8% |
| 20 VUs | 35.1-35.8% | **47.6%** |

El CPU sube de forma clara y proporcional con la concurrencia, pero **no
cruzó el umbral de autoscaling (60%)** — `desiredCount`/`runningCount` se
mantuvieron estables en 1/1 todo el simulacro (nota: en este segundo intento
`desiredCount` partió de 1, no de 2 como en el primero, por el
`desiredCount` por defecto del redeploy).

**Por qué no se cruzó:** no fue falta de capacidad del backend — fue el rate
limiter (`60/minute` en `subir_documento`) frenando el tráfico real desde una
sola IP de origen (393 de 2207 requests terminaron en `429`). Para forzar
más CPU haría falta distribuir la carga desde múltiples orígenes/IPs, lo cual
queda fuera del alcance de este runbook.

**Decisión aceptada:** no se valida un evento de scale-out real con este
método. La tarea y su condición no bloqueante se mantienen en
[P09](../produccion/PENDIENTES_PRODUCCION.md#p09). Lo que sí queda confirmado: el backend escala su uso de CPU
de forma predecible con la concurrencia, sin degradación de latencia ni
errores, hasta el techo que impone el propio rate limiter.

<a id="ecs"></a>
## 5. Circuit Breaker en despliegues (ECS) por `healthCheckGracePeriod` insuficiente

### Contexto

Al desplegar el fix de concurrencia de la sección 3 a staging (2026-09-20/21),
el deploy de CDK falló repetidamente en **Frontend y Portal** con
`ECS Deployment Circuit Breaker was triggered`, mientras Backend y Keycloak
sí completaban. CloudFormation revierte automáticamente todo el stack cuando
esto pasa (`circuitBreaker: { rollback: true }` en `buildService`).

### Causa raíz encontrada

En `infra/sagrilaft/lib/constructs/ecs-fargate.ts`, solo **Keycloak** tenía
`healthCheckGracePeriod` configurado (300s) — Backend, Frontend y Portal no
tenían ninguno (el default real de ECS resultó ser 60s, no 0s como se asumió
en un primer momento). El target group del ALB necesita **5 chequeos
consecutivos exitosos cada 30s (~150s)** para marcar una tarea como
"Healthy". Sin grace period suficiente, el Circuit Breaker puede matar una
tarea sana antes de que el target group llegue a confirmarlo — se confirmó
en logs: contenedores respondiendo `200 OK` reiteradamente y aun así
terminados por rollback.

### Diagnóstico paso a paso (si se repite)

1. `aws cloudformation describe-stack-events --stack-name SagrilaftStack-<env>`
   — buscar `ECS Deployment Circuit Breaker was triggered` y qué servicio.
2. Revisar los logs del contenedor de ese servicio en la ventana del fallo
   (`aws logs get-log-events`) — si muestra respuestas `200 OK` al
   healthchecker del ELB (`ELB-HealthChecker/2.0`) hasta el momento en que
   recibe `SIGQUIT`, es este mismo patrón (contenedor sano, matado de todos
   modos), no un error real de la aplicación.
3. Verificar el grace period real vs. el necesario:
   `aws ecs describe-services --query "services[0].healthCheckGracePeriodSeconds"`.

### Fix aplicado

- Backend: `healthCheckGracePeriod: 180s` (commit `7760859`).
- Frontend/Portal: primero `180s` (commit `7760859`) — **insuficiente en la
  práctica** (se observó una tarea con 3/5 chequeos exitosos, ~131s de vida,
  terminada antes del quinto). Subido a `300s` (commit siguiente), mismo
  valor ya probado en Keycloak. Con `300s`, el deploy completó
  exitosamente el 2026-09-21 (`UPDATE_COMPLETE`, los 4 servicios en
  `Running:1`, `/health` reportando el commit del fix).

### Lección operativa: no interrumpir un deploy en curso

Uno de los ciclos de fallo (el primero) no fue causado por el Circuit
Breaker en sí, sino por una **cancelación manual** del comando
`npm run deploy:staging` (`Ctrl+C`) ~70 segundos después de lanzarlo, antes
de que las tareas nuevas tuvieran tiempo de estabilizarse
(`UPDATE_ROLLBACK_IN_PROGRESS | User Initiated` en los eventos de
CloudFormation). Esto forzó un rollback que, para Frontend/Portal (con el
grace period viejo de 60s), tardó **13 minutos** en resolverse solo y en un
caso dejó el stack en `UPDATE_ROLLBACK_FAILED` (requirió
`aws cloudformation continue-update-rollback` para destrabarlo).

**Regla operativa:** una vez lanzado `cdk deploy`/`npm run deploy:staging`,
dejarlo correr hasta el final (puede tardar 10-15 minutos con los grace
periods actuales) — interrumpirlo a mitad de camino puede dejar el stack en
un estado más difícil de recuperar que esperar a que termine, incluso si
termina en un Circuit Breaker real.

<a id="restauracion"></a>
## 6. Restauración de backup RDS

### Contexto

La instancia de staging (`<INSTANCIA_RDS_STAGING>`)
tiene `deletionProtection: true`, `RemovalPolicy.RETAIN` y 7 días de retención
de backups automáticos. Nunca se restaura sobre la instancia original — siempre
a una instancia nueva y separada, que se elimina al terminar la verificación.

La subnet de base de datos **no tiene ruta a Internet Gateway** (verificado:
route tables `rtb-0ad8ff2f346ca3091` y `rtb-0934198f761154e6e` sin ruta
`0.0.0.0/0`), así que no es posible exponer una instancia restaurada
públicamente para verificarla con un cliente SQL externo. La verificación debe
hacerse desde dentro de la VPC, reutilizando la red del cluster ECS.

### Procedimiento validado (simulacro 2026-09-19)

1. **Identificar el snapshot a restaurar.** Se usó el automático más reciente
   en vez de crear uno manual, para simular un escenario real de recuperación:
   ```bash
   aws rds describe-db-snapshots \
     --db-instance-identifier <INSTANCIA_RDS_STAGING> \
     --query "DBSnapshots[].[DBSnapshotIdentifier,SnapshotCreateTime]" --output table
   ```
   Snapshot usado: `rds:<SNAPSHOT_RDS_STAGING>`.

2. **Restaurar a una instancia nueva**, mismo subnet group y Security Group
   de RDS que el original (ese SG ya permite entrante 5432 solo desde el SG
   de ECS Fargate — no fue necesario tocar ningún Security Group):
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier sagrilaft-staging-restore-drill-<fecha> \
     --db-snapshot-identifier <snapshot-id> \
     --db-instance-class db.t3.micro \
     --db-subnet-group-name <SUBNET_GROUP_RDS_STAGING> \
     --vpc-security-group-ids sg-036466b7555f2e5dd \
     --no-multi-az --no-publicly-accessible \
     --db-parameter-group-name default.postgres16 \
     --tags Key=Purpose,Value=runbook-restore-drill Key=DeleteAfter,Value=<fecha>
   aws rds wait db-instance-available --db-instance-identifier sagrilaft-staging-restore-drill-<fecha>
   ```
   Tiempo real observado: **creación hasta `available` ≈ 10-15 minutos**
   (RTO de referencia para este tamaño de instancia/almacenamiento).

3. **Verificar integridad desde dentro de la VPC**, con una tarea ECS puntual
   sobre la misma task definition de migración (`sagrilaft-staging-migration`),
   sobreescribiendo `DATABASE_HOST` para apuntar al endpoint de la instancia
   restaurada y el `command` para correr un chequeo de solo lectura (no se
   ejecuta ninguna migración contra la copia restaurada):
   ```bash
   aws ecs run-task \
     --cluster sagrilaft-staging \
     --launch-type FARGATE \
     --task-definition <arn de sagrilaft-staging-migration> \
     --network-configuration "awsvpcConfiguration={subnets=[<subnets privadas ECS>],securityGroups=[<sg ECS>],assignPublicIp=DISABLED}" \
     --overrides '{"containerOverrides":[{"name":"migration","environment":[{"name":"DATABASE_HOST","value":"<endpoint restaurado>"}],"command":["sh","-c","<script de verificacion>"]}]}'
   ```
   Este patrón reutiliza exactamente la red y credenciales (`DB_USER`/`DB_PASSWORD`
   desde `sagrilaft/staging/db_credentials`, preservadas por el snapshot) que ya
   usa `scripts/despliegue/run_ecs_migration.sh`, sin exponer nada a Internet.

4. **Resultado del simulacro:**
   - `alembic_version`: `c7a1c1a65662` (esquema consistente, sin drift).
   - `formularios`: 5, `accesos_manuales`: 5, `documentos_adjuntos`: 19,
     `eventos_formulario`: 17 — todas las tablas clave con datos, ninguna vacía.
   - Último evento registrado: `2026-09-18 20:54:55 UTC`, coherente con que el
     snapshot se tomó a las `06:35 UTC` del día siguiente (sin datos faltantes
     ni corrupción aparente).

5. **Limpieza:** eliminar la instancia temporal sin snapshot final (el
   snapshot de origen y los automáticos de 7 días se conservan intactos):
   ```bash
   aws rds delete-db-instance \
     --db-instance-identifier sagrilaft-staging-restore-drill-<fecha> \
     --skip-final-snapshot
   ```

### Conclusión

El backup automático de 7 días **es confiable y restaurable**: RTO observado
~10-15 min para una instancia `db.t3.micro`/100GB, sin pérdida de integridad
detectada. El procedimiento productivo y su RTO se siguen en
[P10](../produccion/PENDIENTES_PRODUCCION.md#p10); el tamaño/clase de instancia
puede diferir de este simulacro.

<a id="herramientas"></a>
## 7. Notas operativas / bugs de herramientas conocidos

- **AWS CLI del sistema roto para algunos comandos con Python 3.14**: comandos
  como `aws sns publish` fallan con `ValueError: badly formed help string`
  (bug de compatibilidad entre el `awscli` empaquetado del sistema y
  `argparse` de Python 3.14, no relacionado con SAGRILAFT). Workaround
  usado: ejecutar la llamada equivalente con `boto3` desde
  `venv/bin/python` en vez de `aws sns publish`. `aws sts get-caller-identity`
  y `aws sns list-topics` sí funcionan normalmente.
- **Blips de DNS transitorios en `docker push` y `cdk deploy`**: se observaron
  errores `dial tcp: lookup ... i/o timeout` y `getaddrinfo EAI_AGAIN` al
  resolver endpoints de ECR/CloudFormation, sin relación con credenciales ni
  con el código. Ambos scripts (`build_and_push_ecr_images.py`, `cdk deploy`)
  son idempotentes — reintentar el mismo comando resuelve el problema.
- **Procesos de simulacro que sobreviven a un corte de sesión**: para scripts
  largos (ej. la prueba de carga, que corre varios minutos), lanzarlos con
  `nohup ... > log 2>&1 < /dev/null & disown` en vez de solo en background
  del harness — así el proceso sigue corriendo en el sistema aunque la sesión
  del agente se interrumpa, y los resultados se pueden recuperar del log
  después.

<a id="ses"></a>
## 8. Salida de sandbox SES y entregabilidad de correo (DKIM, Outlook/Microsoft)

### Aceptación operativa del riesgo — registro del 2026-10-06

El 2026-10-06 el equipo del proyecto registró la aceptación operativa de que
Outlook/Hotmail pueda clasificar algunos mensajes como spam. Gmail y Yahoo
entregan el correo en la bandeja y las verificaciones SPF, DKIM y DMARC son
correctas. El caso con Microsoft sigue abierto y debe mantenerse en
seguimiento. Responsable del registro: equipo del proyecto. La medida definida
es revisar los primeros envíos de producción y mantener abierto el caso con
Microsoft. El requisito de aprobación formal se gestiona en
[P02](../produccion/PENDIENTES_PRODUCCION.md#p02).

**Contexto**: la cuenta AWS SES (`<CUENTA_AWS>`, `us-east-1`) salió de sandbox
(confirmado 2026-09-23 vía `aws sesv2 get-account`:
`ProductionAccessEnabled: true`, `EnforcementStatus: HEALTHY`, cuota
`Max24HourSend: 50000`, `MaxSendRate: 14`). El remitente seguía siendo una
identidad de **email individual** (`legal@blend360.com`) sin DKIM, lo que
perjudica la entregabilidad hacia destinatarios externos reales.

**Cambio implementado**: se cambió el remitente a
`no-reply-sagrilaft@ia.blend360.com` con `Reply-To: legal@blend360.com`
(`backend/infrastructure/notificaciones/email_service.py`,
`backend/infrastructure/config/configuracion.py`, variable nueva
`SMTP_REPLY_TO`). Se descubrió que `ia.blend360.com` **ya tenía una
identidad de dominio verificada en SES fuera de este stack CDK**, con DKIM
en `Status: SUCCESS` desde 2026-07-28 (confirmado vía `aws sesv2
get-email-identity --email-identity ia.blend360.com`). El código en
`infra/sagrilaft/lib/constructs/notifications.ts` se ajustó para
**importar** esa identidad (`ses.EmailIdentity.fromEmailIdentityName`) en
vez de intentar crearla — una identidad de dominio es única por
cuenta+región, y CloudFormation no puede "crearla" si ya existe.

**Dos fallos de deploy encontrados y resueltos en el camino** (útiles como
referencia si se repiten):

1. `UPDATE_FAILED` en `AWS::SES::EmailIdentity` con
   `"Resource ... with identifier 'ia.blend360.com' already exists"`: causado
   por el primer intento, que sí trataba de crear la identidad de dominio vía
   `ses.Identity.publicHostedZone(...)`. Fix: importar en vez de crear (ver
   arriba).
2. `UPDATE_FAILED` en `AWS::ECS::Service` con `"ECS Deployment Circuit
   Breaker was triggered"`: causado por usar `IMAGE_TAG=$(git rev-parse
   HEAD)` **después** de comitear el fix anterior, apuntando a un commit
   para el que nunca se corrió el Paso 1 (build/push a ECR) — ECS no pudo
   hacer pull de esa imagen en ninguno de los 4 servicios. Fix: usar el tag
   del último commit para el que sí se subieron las 4 imágenes a ECR, no
   `git rev-parse HEAD` a ciegas. Regla operativa: si el commit nuevo solo
   toca `infra/`, se puede reutilizar el tag de imagen anterior sin
   rebuildear; si toca `backend/`/`frontend/`/`portal-interno/`, hay que
   repetir el Paso 1 con el HEAD actual antes de desplegar.

**Resultado de pruebas de entregabilidad reales (2026-09-23)**, enviando un
correo de "acceso creado" (con PIN) desde el portal interno de staging hacia
cuentas externas reales:

| Proveedor | Resultado | Detalle |
|---|---|---|
| Gmail | Bandeja de entrada | — |
| Yahoo | Bandeja de entrada | — |
| Outlook/Hotmail (2 cuentas distintas) | **Spam/Correo no deseado** | `SCL: 5`, pese a que SPF, DKIM (`ia.blend360.com` y `amazonses.com`), DMARC y `compauth` pasan (`reason=100`) |

Como 2 de 3 proveedores entregan bien y solo Microsoft clasifica como spam
con autenticación 100% correcta, se descarta un problema de configuración
DNS/SES y se confirma que es la heurística de Microsoft para dominios
remitentes nuevos (reputación de dominio/IP compartida de SES ante
Microsoft específicamente, no un problema general). **Acción registrada**: se
reportó el caso a Microsoft vía
`https://sendersupport.olc.protection.outlook.com/pm/troubleshooting.aspx`
(IP `54.240.8.23`, dominio `ia.blend360.com`) — sin fecha garantizada de
resolución. El seguimiento de aceptación y la condición de prueba corporativa están
centralizados en [P02](../produccion/PENDIENTES_PRODUCCION.md#p02).

**Hallazgo adicional — seguimiento [P14](../produccion/PENDIENTES_PRODUCCION.md#p14)**:
`aws sesv2 get-account` reveló que el caso de uso de producción de SES
registrado ante AWS para esta cuenta corresponde a un proyecto distinto al
actual (`WebsiteURL`/`UseCaseDescription` desactualizados). El envío a
distintos dominios ya funciona en producción (no es una limitación técnica),
pero se abrió un ticket interno para que quien administre la cuenta AWS a
nivel de organización actualice el caso de uso declarado y evite riesgo de
revisión futura por parte de AWS, dado que la cuenta es compartida entre
varios proyectos.

<a id="zoho"></a>
## 9. Migración de cuenta oficial de Zoho Sign y bugs reales del webhook

**Contexto**: se reemplazó la cuenta operativa de Zoho Sign (asociada a
`<correo-interno>`) por la cuenta oficial de Legal para producción
(`sagrilaft/prod/zoho_credentials`), y se validó primero en staging
(`ZOHO_SIGN_TESTING=true`, sin consumir créditos reales) antes de confiar en
ella para el corte a prod.

**Bootstrap del secreto de prod sin desplegar el stack**: como producción
nunca se ha desplegado, `sagrilaft/prod/zoho_credentials` no existía
todavía (lo crea CDK). Se creó manualmente por fuera de CDK
(`aws secretsmanager create-secret`) para no bloquear la carga de
credenciales. Riesgo dejado documentado: cuando se ejecute el bootstrap
real de prod, CDK intentaría *crear* ese mismo secreto y fallaría con
`AlreadyExists` (mismo patrón que el incidente de la identidad SES, sección
8). Se corrigió `infra/sagrilaft/lib/constructs/secrets.ts` con el flag
`zohoSecretYaExiste` (default `false`): si es `true`, el secreto se
**importa** en vez de crearse. Recordar pasar `-c zohoSecretYaExiste=true`
en el primer `npm run deploy:prod:bootstrap`.

**Validación en staging con NAT Gateway temporal**: la arquitectura no
tiene NAT Gateway por diseño (VPC endpoints para servicios AWS, ver sección
8/`ARQUITECTURA_CORE.md`), pero Zoho Sign es una API externa real — sin NAT
una tarea ECS en subred privada no tiene ninguna ruta a internet hacia
`sign.zoho.com`/`accounts.zoho.com`. Confirmado con `ConnectTimeout` en los
3 reintentos y `aws ec2 describe-nat-gateways` vacío sobre la VPC de
staging. Se descubrió en el camino que **`deploy:prod`/`deploy:prod:bootstrap`
tampoco activaban el NAT** (mismo default `false`) — corregido agregando
`-c habilitarNatEgress=true` a ambos scripts en
`infra/sagrilaft/package.json` (y a `synth:prod`/`diff:prod` para
consistencia). Para staging, el NAT se activó **temporalmente** vía
`npm run deploy:staging -- -c habilitarNatEgress=true` (sin modificar el
script por defecto) — tiene costo recurrente (~$32-45/mes + tráfico)
mientras quede activo; apagarlo con un `npm run deploy:staging` normal
cuando ya no se necesite.

**Reactivación y apagado del 2026-10-20.** El NAT se volvió a activar temporalmente
para repetir la validación del webhook recreado (ver adenda más abajo). Efecto
colateral no buscado: `deploy:staging` trae `-c bedrockModelId=${BEDROCK_MODEL_ID:-amazon.nova-pro-v1:0}`,
y al no exportar esa variable en esa sesión, staging pasó de `claude-sonnet-4-6` a
`amazon.nova-pro-v1:0` — ver [MATRIZ_AWS_CONFIG.md](../produccion/configuracion/MATRIZ_AWS_CONFIG.md).
Una vez confirmada la firma real, se apagó con `cdk deploy` manual (mismo imageTag
real desplegado, `-c habilitarNatEgress=false`, sin `deploy_release.py` porque no
había migración ni cambio de imagen de por medio). Verificado: NAT Gateway en
estado `deleted`, stack `UPDATE_COMPLETE`, los 4 servicios ECS `ACTIVE` con
`rolloutState=COMPLETED` sin caída, `/health` respondiendo en el mismo commit.
El diff aplicado solo tocó el NAT Gateway, su EIP, dos rutas por defecto y el
tag `Private`→`Isolated` de las subredes privadas (sin reemplazo); el resto del
diff fue el ruido de tildes ya documentado en ECR/alarmas, sin relación con este
cambio.

**Bug 1 — firma HMAC del webhook siempre rechazada (403)**: al recibir el
primer webhook real de Zoho (nunca antes se había probado contra Zoho real;
el test automatizado usa un doble simulado), se rechazaba con
`SECURITY event=WEBHOOK_TOKEN_INVALID`. Causa: `_normalizar_firma`
(`backend/api/routers/webhooks.py`) recortaba cualquier valor que
contuviera `"="` y no empezara con `"sha256="`, quedándose con lo que
hubiera *después* del último `"="`. La firma real de Zoho viene en base64
con padding (ej. `"...jO4m6Vvo="`), así que esa lógica la dejaba vacía
siempre — ninguna firma podía coincidir jamás, sin importar que el
`webhook_secret` fuera correcto. Confirmado con un log de diagnóstico
temporal: `header_bruto='hy020yEBI...1nc=' normalizada=''`. Fix: solo
quitar el prefijo opcional `"sha256="`, no tocar nada más. Test de
regresión: `tests/unit/test_webhooks_hmac.py`.

**Bug 2 — webhook validado pero el formulario no se completaba**: tras el
fix del Bug 1, el webhook pasaba la validación (200 OK) pero el formulario
seguía en `PENDIENTE_FIRMA` — solo cambiaba a `FIRMADO` con el botón de
verificación manual. Causa: `procesar_webhook_verificado`
(`backend/services/firma/firma_service.py`) comparaba
`request_status == "Completed"` (capitalizado), pero Zoho real manda
`request_status` en minúscula (`'completed'`, confirmado en logs reales).
El test de integración existente construía su payload de prueba con
`"Completed"` — el mismo valor que el código esperaba — por lo que nunca
detectó el problema. Fix: normalizar con `.lower()` antes de comparar
(aplica también a `declined`/`expired`). Test de regresión:
`tests/unit/test_webhook_status_casing.py`.

**Resultado final validado en staging (2026-09-24)**: expediente real
enviado a firma → firmado por el destinatario → webhook recibido, validado
y procesado automáticamente (sin verificación manual) → formulario en
`FIRMADO`, documento descargado y guardado en S3, correo de notificación
enviado. Un segundo webhook duplicado (`RequestCompleted`, reenvío típico
de Zoho) fue ignorado correctamente como idempotente
(`"Webhook duplicado ignorado: formulario ... ya está FIRMADO"`).

**Lección operativa**: dos bugs reales (HMAC y casing) sobrevivieron sin
detectarse porque los tests automatizados construían sus payloads de
prueba con el mismo formato que el código esperaba, no con el formato real
que Zoho realmente envía. Cualquier integración externa nueva debería, en
algún punto antes de confiar en producción, probarse contra el proveedor
real al menos una vez — un doble/mock nunca va a reproducir un desajuste
de formato entre "lo que el proveedor real envía" y "lo que el código
asume".

**Actualización 2026-10-20 — webhooks recreados y `.env*` reconciliados.** Los webhooks
`Sagrilaft-Produccion` y `Sagrilaft-Staging` configurados en septiembre ya no estaban en
la cuenta de Zoho Sign (se habían borrado); se confirmó que es la misma cuenta de
entonces (Client ID/Secret del Self Client coinciden con `sagrilaft/{env}/zoho_credentials`
en AWS), así que el `refresh_token` sigue siendo válido y no hizo falta re-autorizar nada.
Se recrearon ambos webhooks con la misma configuración (URL, eventos, firma HMAC
SHA-256 con el `webhook_secret` ya existente en cada secreto). De paso se corrigió
`.env.prod`/`.env.staging`, que tenían la cuenta operativa anterior a la migración de
septiembre — ver [condición de bloqueo](../produccion/despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod).
Confirmado con una firma real en staging el mismo día: expediente `SAG-9C58BEF6`, cuatro
entregas del webhook con `200 OK`, expediente pasó a `FIRMADO` sin tocar nada manual.

**Bug 3 — el portal interno no reflejaba la firma sin recargar.** Durante esa misma prueba
se detectó que, aunque el webhook ya actualizaba el backend, el detalle del expediente en el
portal interno solo se consultaba una vez al cargar la página: el banner se quedaba en
"Firma electrónica pendiente" hasta F5 o el botón "Verificar estado". No era un problema del
webhook ni del backend — el frontend nunca volvía a preguntar. Fix:
`useExpedienteDetalle.js` ahora consulta el expediente cada 10 segundos mientras el estado
sea `pendiente_firma`, y deja de hacerlo en cuanto cambia. Probado en local (polling visible
en logs, UI cambia sola) y en staging (release `767b3acdc36044869d07980210e2ff212311474e`,
desplegada con `deploy_release.py`): el banner pasó solo a "Documentos firmados" durante la
firma real descrita arriba, sin recargar la página.


<a id="despliegue-coordinado"></a>
## Despliegue coordinado: diagnóstico y límites de recuperación

**Laboratorio P20:** A/B/C no requieren dominios nuevos, HTTPS de navegador ni
login. El lanzador corregido localmente impone el fixture sin DDL en los dos
subcasos de A, incluida pérdida del observador; no usar el comando ordinario de
migración para simular incertidumbre. Reconciliar el ARN existente y preservar
el lock; no relanzar, recuperar ni liberarlo sin la autorización correspondiente.
Usar únicamente `p20_operation=scenario-a-fixture` para estos subcasos; el
flujo general rechaza fault injection. Sin `--execute` no toma lock ni lanza
tareas. La ruta ejecutable retiene el lock incluso ante el fallo esperado;
reconciliarlo requiere autorización separada y nunca borrado incondicional.
La corrección se validó después en AWS: A cerrado con excepción externa propia;
B cerrado con expansión, fallo de salud, rollback, smoke y liberación condicional
comprobados, con excepción externa propia; C preparado solo localmente y no ejecutado. No repetir las pruebas completadas. Consultar restricciones,
ENTRYPOINT/digest y evidencias en el [plan de A](../produccion/p20/PLAN_OPERATIVO_RECUPERACION_P20.md#preparación-específica-del-escenario-a).


El orquestador local registra la evidencia por intento y usa el objeto
`_deployment/<stack>.lock` en el bucket del stack. Ante fallo, timeout o interrupción,
conserva el bloqueo; no inicia por sí solo una recuperación ni libera el lock
por expiración. ECS/CloudFormation sí pueden hacer rollback automático del
despliegue (comprobado en B); esto no revierte Alembic ni libera el lock.
No inferir de ello autorización para reintentar. Su ensayo AWS se sigue en
[P20](../produccion/PENDIENTES_PRODUCCION.md#p20).

Antes de decidir una recuperación, conservar plan, eventos, ARN/resultado de tarea,
digests, evidencia Alembic y estado de CloudFormation/ECS. Determinar si la migración
terminó y qué esquema quedó. No borrar el lock ni relanzar una migración solo por
haber pasado tiempo. La reconciliación y liberación requieren un procedimiento
revisado y autorización para la acción concreta.

El rollback ECS/CloudFormation no deshace Alembic ni recupera datos. Volver a una
imagen anterior publicada exige compatibilidad con el esquema resultante; no
reconstruirla ni aplicar downgrade automáticamente. Cambios incompatibles necesitan
mantenimiento/corrección o recuperación ensayada. Estos límites no alteran los
simulacros históricos documentados arriba.

En modalidad manual de staging, salida 3 y `manual_validation_pending` indican una
activación verificada pendiente del operador, no un despliegue fallido. El lock sigue
reservado. Completar y revisar la evidencia según la
[guía](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md#smoke-manual); no relanzar el deploy.
Si falla el smoke, registrar `failed` y conservar el bloqueo para recuperación.
Si falla o se interrumpe el cierre después de solicitar DeleteObject, su resultado
puede ser incierto: reconciliar el objeto S3 y la evidencia antes de cualquier reintento.
No hay reparación automática ni garantía de que un fallo local posterior a DeleteObject
implique que el lock siga presente. El cierre no vuelve a consultar la revisión viva
RDS: conserva la evidencia Alembic de esa ejecución y exige coordinación exclusiva.
