# Estado de staging y producción

Función única: resumir la situación de los ambientes y enlazar sus evidencias.
No contiene backlog ([Pendientes](../produccion/PENDIENTES_PRODUCCION.md)) ni
instrucciones de despliegue ([guía](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md)).

## Estado actual — verificado el 2026-11-23

Verificado con consultas de solo lectura a AWS, `/health` y git el 2026-11-23
(después de la release de la tarde). No es una consulta en vivo: si pasó tiempo,
volver a verificar antes de decidir.

### Producción

**Activa, sin abrir a usuarios reales.** Falta el Go final (P02) y las pruebas
productivas P05, P06 y P07 ([Pendientes](../produccion/PENDIENTES_PRODUCCION.md#corte)).

| Componente | Estado | Cómo se verificó |
|---|---|---|
| Versión | `972f99312050e13e759b1d6d8562d7707386c7d9` (release del 2026-11-23) | `/health` y definiciones de tarea ECS |
| Esquema de base de datos | Revisión Alembic `n54c67d890eb` (sin cambios en la release del 23-nov) | Registro de la release (`release_execute.log`) |
| Stack `SagrilaftStack-prod` | `UPDATE_COMPLETE` (2026-11-23 20:05 UTC) | `describe-stacks` |
| Servicios ECS | backend, formulario, portal y Keycloak con 1 tarea cada uno; el trabajador de listas existe desde el 2026-11-18 y está en 0 | `describe-services` |
| Backend | 2 GB de memoria (desde el 2026-11-23); autoescalado entre 1 y 2 copias | Definición de tarea `backend:8` y `describe-scalable-targets` |
| Base de datos | `db.t3.small`, PostgreSQL 16.13, una sola zona, 14 días de copias automáticas, cifrada, no pública, protección contra borrado activa | `describe-db-instances` |
| Copias manuales | `sagrilaft-prod-base-pre-pruebas-20261123` y `sagrilaft-prod-pre-ip-cliente-20261123` | `describe-db-snapshots` |
| Lock de despliegue (S3) | Libre | `head-object` sin objeto |
| Alarmas | 16, todas en `OK`; avisan por SNS al fallar y al recuperarse | `describe-alarms` |
| Destinatarios de alertas | 1 suscripción de correo, confirmada | `list-subscriptions-by-topic` |
| IP real del cliente | `TRUSTED_PROXY_IPS=10.0.0.0/16`; dos intentos de prueba se registraron con la IP real | Parámetro SSM y registros del backend |
| Proveedor de listas | `deshabilitado` (el código no permite otro valor en producción) | Parámetro SSM y `backend/infrastructure/config/configuracion.py` |
| Firma Zoho | Sin firmas en producción. Único intento: 2026-11-03 17:09 UTC, rechazado por falta de créditos de API. Sin llamadas al webhook | Registros del backend (se guardan 30 días) |
| Tags de release en git | Ninguno | `git tag` y `git ls-remote --tags` |

**Historial de releases de producción** (de las definiciones de tarea del backend en ECS):

| Fecha | Versión | Evidencia disponible |
|---|---|---|
| 2026-10-07 | Bootstrap (imagen provisional, servicios en 0) | No conservada; queda el registro de CloudFormation ([detalle](../evidencia/README.md#bootstrap-prod-20261007)) |
| 2026-10-21 | `f8d9dcf` — primer corte, migración a `f8a9b0c1d2e3` | [Recuperada](../evidencia/primer-corte-prod-20261021/README.md) |
| 2026-10-30 | `58125cb` — corrige el arranque de nginx en los frontends | Sin evidencia archivada; quedan ECS y las versiones del lock en S3 ([detalle](../evidencia/README.md#sin-evidencia)) |
| 2026-11-03 | `84ca98e` — mensaje claro cuando Zoho no tiene créditos | Sin evidencia archivada; quedan ECS y las versiones del lock en S3 ([detalle](../evidencia/README.md#sin-evidencia)) |
| 2026-11-18 | `d4cdb84` — adaptador de listas y migración a `n54c67d890eb` | `tmp/despliegue-prod-20261118/` (fuera del control de versiones) |
| 2026-11-23 | `972f993` — IP real del cliente y 13 alarmas nuevas, sin migración | `tmp/despliegue-prod-20261123/RESUMEN.md` (fuera del control de versiones) |

Cambios de infraestructura sin release de imagen: etiquetado y autoescalado
(2026-11-18), 2 GB de memoria y 14 días de copias (2026-11-23).

### Staging

**Apagado** desde el 2026-11-23: servicios en 0 y base de datos detenida
(`describe-services`, `describe-db-instances`). Última release: `02d3ea9`
(2026-11-23), que probó la IP real y las alarmas antes de producción
(`tmp/ip-cliente-staging-20261123/RESUMEN.md`). Base de datos `db.t4g.small`,
7 días de copias. Se enciende y apaga con `scripts/aws/staging_encendido.sh`.

## Decisiones de operación vigentes

- El despliegue CDK sigue siendo manual por decisión del 2026-09-29.
- Se prepara producción con listas deshabilitadas hasta contratar proveedor;
  lo que falta para activarlo está en los [pendientes del módulo de listas](../listas/OPERACION_PRUEBAS_Y_PENDIENTES.md#7-pendientes).
- La aceptación operativa del riesgo Outlook fue registrada el 2026-10-06.
  El registro formal y su seguimiento se gestionan en [P02](../produccion/PENDIENTES_PRODUCCION.md#p02).

## Histórico (registros hasta el 2026-10-24)

Lo que sigue es el registro original, sin cambios de contenido. Describe el estado
en esas fechas, no el actual. Las evidencias del primer corte y de SNS del 21 de octubre
se recuperaron; las del bootstrap y la release de staging `6542326` no se conservan
y sus enlaces llevan a la explicación con las fuentes alternativas
([índice de evidencia](../evidencia/README.md)).

*Encabezado original:* Última revisión documental: 2026-10-21 (credenciales SMTP/Zoho y release del 20 de
octubre); el resto se basa en evidencias archivadas del 15–16 de octubre y
referencias acreditadas posteriores al registro inicial del 6 de octubre. Función única: resumir la situación
acreditada de los ambientes y enlazar sus evidencias. No contiene un backlog
ni instrucciones de despliegue. No es una consulta en vivo de AWS.

### Staging

**Operativo y validado funcionalmente.** Bootstrap, infraestructura, secretos,
S3, imágenes y migración ECS fueron registrados como realizados; la migración
terminó con `ExitCode=0`. Los portales y Keycloak fueron probados.

La [ejecución AWS del 1, 5 y 6 de octubre](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md)
acredita el recorrido desde acceso hasta firma, auditoría y cierre. La
[validación PostgreSQL local](../evidencia/e2e-staging/VALIDACION_STAGING_E2E.md)
es una evidencia distinta, con dobles para integraciones externas.

#### Release del 20 de octubre de 2026 — `767b3acdc36044869d07980210e2ff212311474e`

Desplegada con `deploy_release.py` (modo `compatible`, sin migración nueva: misma
revisión Alembic `f8a9b0c1d2e3` antes y después). Corrige que el portal interno no
reflejaba el cambio de estado de firma sin recargar la página. Probado con una firma
real: expediente `SAG-9C58BEF6`, webhook de ZohoSign con cuatro entregas en `200`, y
el banner pasó solo de "pendiente" a "Documentos firmados" sin F5. Smoke manual
completo (`release_sha`, `crear_y_leer_correo`, `guardar_y_recuperar`,
`borrador_con_correo`), evidencia registrada en `manual-validation.json` y archivos
en `manual-evidence/` del directorio de ejecución. Cierre formal con `--close-manual
--execute`: `release_completed`, lock de S3 liberado (confirmado con `404` posterior).
Detalle: [runbook, sección Zoho](../operacion/RUNBOOK_OPERATIVO.md#zoho).

El NAT Gateway que se había reactivado para esta validación se apagó el mismo día con
`cdk deploy` manual (`-c habilitarNatEgress=false`). Verificado: NAT en estado
`deleted`, stack `UPDATE_COMPLETE`, los 4 servicios ECS `ACTIVE`/`COMPLETED` sin
interrupción, `/health` respondiendo en el mismo commit tras el cambio.

#### Actualización del 6 de octubre de 2026

ECR quedó en `IMMUTABLE` para backend, formulario público, portal interno y Keycloak.
El stack terminó en `UPDATE_COMPLETE` a las 15:54:14 de Bogotá; eventos y plantilla
final acreditan únicamente los cuatro cambios de mutabilidad. Retención intacta.
El informe y la evidencia JSON de esa actualización no están archivados en el repositorio; la release posterior se documenta en [la carpeta de evidencia de la release](../evidencia/README.md#release-staging-6542326) (no conservada).
La actualización aislada de ECR no publicó imágenes ni ejecutó migraciones.
Posteriormente, el operador publicó las cuatro imágenes candidatas con SHA
`6542326a67d664847b3ff99bd8ec3c82ca3a7c6b`. El [manifiesto archivado](../evidencia/README.md#release-staging-6542326) (no conservada)
registra `complete: true` y los cuatro digests; sus campos y huellas de build fueron
verificados localmente. Ese manifiesto aislado no acreditaba activación ni actualización de BD.
Después, el intento 3 del 6–7 de octubre completó migración c7→f8, activación
y verificación de cuatro servicios/digests y aceptación manual
([evidencia no conservada](../evidencia/README.md#release-staging-6542326)).
No se volvieron a consultar los recursos de staging en esta actualización.

Consultas de solo lectura previas del mismo día, registradas en la sesión de trabajo
(sin un archivo de captura independiente enlazado aquí):

- Backend: task definition `sagrilaft-staging-backend:44`; tag y `GIT_SHA`
  `ff0061a39166c549084e1a55769c172104eac86b`; digest
  `sha256:7240b014dda427005993fd82773c9f509cd72b5ee649ad3bb0f33503d15849fa`.
- RDS PostgreSQL 16.13: revisión `c7a1c1a65662`; columna
  `accesos_manuales.correo_destinatario` existente y nullable. El único salto al
  head `f8a9b0c1d2e3` agrega NOT NULL; no elimina columnas ni tablas.
- Código desplegado compatible en los flujos API revisados: correo obligatorio
  validado por EmailStr. La defensa adicional del repositorio contra None/vacío
  está en el checkout local; no se afirma que esa defensa esté desplegada.

Estas observaciones no acreditan el estado futuro ni sustituyen la revalidación
previa a una ejecución. El cambio ECR no modificó ese esquema ni la release activa.

#### Trazabilidad de versiones

| Registro histórico | Alcance |
|---|---|
| `dc6594713005ea97be6499ab219ecff9ef83d1ea-staging-dummy` | Tag registrado en la documentación inicial de staging; no representa necesariamente la versión actual. |
| `ef4024fe579a9e0827daf3c8099ecf26e1e2d2e7` | Deploy registrado el 2026-09-23, duración 693,17 s; `/health` reportó ese commit y `database=ok`, `sns_alertas=ok`. |
| E2E del 5–6 de octubre | Evidencia funcional posterior sin asociación inequívoca al SHA de las imágenes. Seguimiento: [P01](../produccion/PENDIENTES_PRODUCCION.md#p01). |

### Producción

**Migración y activación completadas y verificadas (2026-10-21); apertura a usuarios aún no acreditada.**
El [bootstrap del 7 de octubre](../evidencia/README.md#bootstrap-prod-20261007) (no conservada)
registró CREATE_COMPLETE, RDS disponible y cuatro servicios en 0/0/0.

**Actualización del 2026-10-21 (primer corte).** Con el SHA `f8d9dcf06dcfee43d6b885827444ffcee9f2007b`,
`deploy_release.py --execute` migró la base (revisión Alembic de `[]` a `f8a9b0c1d2e3`, verificada)
y activó los cuatro servicios (`desired=1 running=1`, digests aprobados coincidentes). CloudFormation
terminó en `UPDATE_COMPLETE`. El cliente `cdk deploy` falló después por un error de red
(`ECONNRESET`), no por un fallo real; el orquestador se detuvo antes de sus propias verificaciones
y **el lock de S3 quedó tomado, sin reconciliar** (se reconcilió y liberó el 2026-10-24; ver [P04](../produccion/PENDIENTES_PRODUCCION.md#p04)). La verificación se hizo de forma independiente:
CloudFormation, los 4 servicios ECS, los target groups del ALB y un smoke externo manual
(12/12 comprobaciones: HTTPS, HSTS, redirección, `/health` y OIDC) confirman que producción está
activa y saludable. [Evidencia completa](../evidencia/primer-corte-prod-20261021/README.md).
No se ha abierto a usuarios; faltan P05, P06, P07 y el Go final de Andrés Hurtado.

**Seguridad de acceso (2026-10-24).** La consola admin de Keycloak (`/admin/master/console/`) es
alcanzable desde internet. La protección de fuerza bruta se configuró manualmente en los realms `master`
y `sagrilaft` (reportado por el responsable, no verificado por el asistente). El WAF tiene una regla
nueva para `/admin` y `/realms/master`, desplegada en **staging** y en **producción** el 2026-10-24.
En staging se verificó el bloqueo real (`403` y métricas del WAF); en producción se verificó la regla
en vivo y que el resto del servicio no cambió. Detalle en
[P08](../produccion/PENDIENTES_PRODUCCION.md#p08).

Verificado el 2026-10-16 con lecturas de solo metadatos y comparación de igualdad, sin valores:

- `SagrilaftStack-prod` en `CREATE_COMPLETE`; los cuatro servicios ECS en 0/0/0. Ninguna tarea activa.
- `cdk diff` con los argumentos del bootstrap: sin diferencias. Lo desplegado coincide con el código del bootstrap.
- Secretos de CDK en producción (`app_secret`, `keycloak_admin`, `db_credentials`) sin cambios respecto a su escritura por CloudFormation (7 de octubre). Su fuente vigente es AWS. El 2026-10-19 se eliminaron de `.env.prod` sus claves locales (`SECRET_KEY`, `KEYCLOAK_ADMIN*`, `KEYCLOAK_DB_*`), que ningún script leía.
- **Staging, `db_credentials` (auditado el 2026-11-03, solo lectura).** El secreto no coincide con la forma de producción. Su historial, verificado en CloudTrail y en las versiones del secreto:
  - 2026-08-18 12:12: creado por CloudFormation con `username` y `password` (32 caracteres).
  - 2026-08-18 12:21: el `SecretTargetAttachment` escribió las 7 claves, igual que en producción.
  - 2026-08-18 16:56 y 16:59: edición manual del secreto (contraseña de 64 caracteres, sin las 5 claves de metadatos), seguida de `ModifyDBInstance` manual sobre RDS.
  - 2026-10-28 14:39 y 14:56: nueva edición manual (contraseña de 65 caracteres) y `ModifyDBInstance` manual sobre RDS.
  - 2026-11-03: backend y migración conectaron a la base en el primer intento con la contraseña actual.

  Staging tiene 2 claves y producción 7 porque la edición manual del 2026-08-18 reemplazó la versión que había escrito el attachment. La edición del 2026-10-28 fue intencional y la hizo el operador desde la consola. El motivo de la del 2026-08-18 no está registrado en el repositorio. La app solo usa `username` y `password`, así que la diferencia no afecta la conexión. Detalle en [MATRIZ_AWS_CONFIG.md](../produccion/configuracion/MATRIZ_AWS_CONFIG.md).
- Secretos externos escritos manualmente: `zoho_credentials` (24 de septiembre) y `smtp_credentials` (7 de octubre, 09:05). El 2026-10-16 `.env.prod` no coincidía con ninguno; ambos se reconciliaron el 2026-10-20 (viñeta siguiente).
- **Sincronización de secretos: SMTP y Zoho reconciliados (2026-10-20).** SMTP: la identidad real de producción es `ses-smtp-prod-sagrilaft` (no `sagrilaft-ses-smtpp`, la identificada el 2026-10-16), ya con permisos de envío, y `.env.prod` coincide con el secreto vigente en AWS. Zoho: se confirmó en la consola de Zoho que AWS tiene la credencial de la cuenta oficial de Legal; `.env.prod` y `.env.staging` se corrigieron para coincidir, y los webhooks (borrados) se recrearon con firma HMAC. Ambas condiciones de bloqueo quedan cerradas ([P03](../produccion/PENDIENTES_PRODUCCION.md#p03); [detalle](../produccion/despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod)). El webhook recreado se probó con una firma real en staging el mismo día (expediente `SAG-9C58BEF6`, `FIRMADO`); en producción el webhook no se ha probado (P05).

**Actualización del 2026-10-21 (SNS de alertas).** `SagrilaftStack-prod` se actualizó a `UPDATE_COMPLETE` con el código `2b0b844e66d8efafcd89fd815a179a6cf14a04dc`: se agregó la suscripción de `Bryan.Ariza@blend360.com` (confirmada) y se actualizó el parámetro `ALERTAS_EMAIL_DESTINATARIO` a 12 correos. Las alarmas de producción están en `OK`. Las once suscripciones originales siguen en CloudFormation pero no existen en SNS (drift); no se ha enviado invitación a esos destinatarios. Decisión del mismo día: la lista de alertas queda solo con `Bryan.Ariza@blend360.com` (SNS y SES) hasta autorizar a los otros once. Esa decisión se aplicó en un segundo `cdk deploy` (`UPDATE_COMPLETE`, 12:24 UTC): los once recursos obsoletos se eliminaron de CloudFormation sin errores, SSM quedó con un solo correo y los servicios siguen en 0/0/0. El SHA del repositorio en ese momento era `a1b1a5cda6635d681c1785d64ea84a2198d10963`. Detalle: [evidencia del 2026-10-21](../evidencia/sns-alertas-prod-20261021/README.md) y [P06](../produccion/PENDIENTES_PRODUCCION.md#p06).

Release, migración, activación y smoke productivos: ver la actualización del 2026-10-21 arriba.
El SHA del primer corte fue `f8d9dcf06dcfee43d6b885827444ffcee9f2007b` (ya no es el vigente: ver «Estado actual»); el del bootstrap original
fue `4f7543123adea6a7da9ebbde187760a930fb1b4e`.

El catálogo de valores/configuración es
[Configuración en AWS](../produccion/configuracion/MATRIZ_AWS_CONFIG.md).
La preparación y ejecución se siguen exclusivamente en
[PENDIENTES_PRODUCCION.md](../produccion/PENDIENTES_PRODUCCION.md#corte).

### Evidencia operativa

Los incidentes corregidos, simulacros y resultados de integraciones están en
el [runbook](../operacion/RUNBOOK_OPERATIVO.md): SNS (sección 1), Zoho/reintentos
(2 y 9), carga (3), autoscaling observado (4), ECS (5), RDS (6) y SES (8).
El [registro de cierres](../produccion/PENDIENTES_PRODUCCION.md#cierres)
identifica qué salió del backlog sin duplicar esos relatos.

Este documento cambia cuando una nueva evidencia modifica el estado de un
ambiente. La prioridad y el cierre de tareas se actualizan en el backlog.
