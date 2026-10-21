# Estado de staging y producción

Última revisión documental: 2026-10-21 (credenciales SMTP/Zoho y release del 20 de
octubre); el resto se basa en evidencias archivadas del 15–16 de octubre y
referencias acreditadas posteriores al registro inicial del 6 de octubre. Función única: resumir la situación
acreditada de los ambientes y enlazar sus evidencias. No contiene un backlog
ni instrucciones de despliegue. No es una consulta en vivo de AWS.

## Staging

**Operativo y validado funcionalmente.** Bootstrap, infraestructura, secretos,
S3, imágenes y migración ECS fueron registrados como realizados; la migración
terminó con `ExitCode=0`. Los portales y Keycloak fueron probados.

La [ejecución AWS del 1, 5 y 6 de octubre](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md)
acredita el recorrido desde acceso hasta firma, auditoría y cierre. La
[validación PostgreSQL local](../evidencia/e2e-staging/VALIDACION_STAGING_E2E.md)
es una evidencia distinta, con dobles para integraciones externas.

### Release del 20 de octubre de 2026 — `767b3acdc36044869d07980210e2ff212311474e`

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

### Actualización del 6 de octubre de 2026

ECR quedó en `IMMUTABLE` para backend, formulario público, portal interno y Keycloak.
El stack terminó en `UPDATE_COMPLETE` a las 15:54:14 de Bogotá; eventos y plantilla
final acreditan únicamente los cuatro cambios de mutabilidad. Retención intacta.
El informe y la evidencia JSON de esa actualización no están archivados en el repositorio; la release posterior se documenta en [la carpeta de evidencia de la release](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/README.md).
La actualización aislada de ECR no publicó imágenes ni ejecutó migraciones.
Posteriormente, el operador publicó las cuatro imágenes candidatas con SHA
`6542326a67d664847b3ff99bd8ec3c82ca3a7c6b`. El [manifiesto archivado](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/ecr-manifest-intento-1.json)
registra `complete: true` y los cuatro digests; sus campos y huellas de build fueron
verificados localmente. Ese manifiesto aislado no acreditaba activación ni actualización de BD.
Después, el intento 3 del 6–7 de octubre completó migración c7→f8, activación
y verificación de cuatro servicios/digests y aceptación manual;
[evidencia y límites](../produccion/PENDIENTES_PRODUCCION.md#p20).
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

### Trazabilidad de versiones

| Registro histórico | Alcance |
|---|---|
| `dc6594713005ea97be6499ab219ecff9ef83d1ea-staging-dummy` | Tag registrado en la documentación inicial de staging; no representa necesariamente la versión actual. |
| `ef4024fe579a9e0827daf3c8099ecf26e1e2d2e7` | Deploy registrado el 2026-09-23, duración 693,17 s; `/health` reportó ese commit y `database=ok`, `sns_alertas=ok`. |
| E2E del 5–6 de octubre | Evidencia funcional posterior sin asociación inequívoca al SHA de las imágenes. Seguimiento: [P01](../produccion/PENDIENTES_PRODUCCION.md#p01). |

## Producción

**Infraestructura base creada; corte funcional y apertura no acreditados.**
El [bootstrap del 7 de octubre](../evidencia/bootstrap-prod-4f7543123adea6a7da9ebbde187760a930fb1b4e/README.md)
registró CREATE_COMPLETE, RDS disponible y cuatro servicios en 0/0/0. Esto
sustituye la descripción anterior de infraestructura no desplegada. No acredita
release funcional, migración, activación o smoke productivo posteriores.
No se revalidó producción en AWS después del 16 de octubre; lo registrado como
producción es documental.

Verificado el 2026-10-16 con lecturas de solo metadatos y comparación de igualdad, sin valores:

- `SagrilaftStack-prod` en `CREATE_COMPLETE`; los cuatro servicios ECS en 0/0/0. Ninguna tarea activa.
- `cdk diff` con los argumentos del bootstrap: sin diferencias. Lo desplegado coincide con el código del bootstrap.
- Secretos de CDK (`app_secret`, `keycloak_admin`, `db_credentials`) sin cambios respecto a su escritura por CloudFormation (7 de octubre). Su fuente vigente es AWS. El 2026-10-19 se eliminaron de `.env.prod` sus claves locales (`SECRET_KEY`, `KEYCLOAK_ADMIN*`, `KEYCLOAK_DB_*`), que ningún script leía.
- Secretos externos escritos manualmente: `zoho_credentials` (24 de septiembre) y `smtp_credentials` (7 de octubre, 09:05). El 2026-10-16 `.env.prod` no coincidía con ninguno; ambos se reconciliaron el 2026-10-20 (viñeta siguiente).
- **Sincronización de secretos: SMTP y Zoho reconciliados (2026-10-20).** SMTP: la identidad real de producción es `ses-smtp-prod-sagrilaft` (no `sagrilaft-ses-smtpp`, la identificada el 2026-10-16), ya con permisos de envío, y `.env.prod` coincide con el secreto vigente en AWS. Zoho: se confirmó en la consola de Zoho que AWS tiene la credencial de la cuenta oficial de Legal; `.env.prod` y `.env.staging` se corrigieron para coincidir, y los webhooks (borrados) se recrearon con firma HMAC. Ambas condiciones de bloqueo quedan cerradas ([P03](../produccion/PENDIENTES_PRODUCCION.md#p03); [detalle](../produccion/despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod)). El webhook recreado se probó con una firma real en staging el mismo día (expediente `SAG-9C58BEF6`, `FIRMADO`); en producción el webhook no se ha probado (P05).

No hay release funcional, migración, activación ni smoke productivo. El SHA vigente para el corte no está fijado todavía; el del bootstrap es `4f7543123adea6a7da9ebbde187760a930fb1b4e`.

El catálogo de valores/configuración es
[checklist-valores-staging-prod.md](../produccion/configuracion/checklist-valores-staging-prod.md).
La preparación y ejecución se siguen exclusivamente en
[PENDIENTES_PRODUCCION.md](../produccion/PENDIENTES_PRODUCCION.md#corte).

## Laboratorio P20 — estado actualizado al 15 de octubre

A, B y C cerrados formalmente con excepciones y evidencias propias, y locks
liberados condicionalmente. C acreditó la incompatibilidad, la restauración del
snapshot a una RDS nueva y un smoke backend aislado GET/PUT/GET con persistencia;
los cuatro servicios ECS quedaron en 0/0/0. El cierre de recuperación no
autoriza limpieza ni equivale a un corte productivo. El laboratorio se retiró el
16 de octubre de 2026 y su infraestructura AWS fue eliminada ([retiro](../produccion/p20/RETIRO_P20.md)).
[Plan y evidencias](../produccion/p20/PLAN_OPERATIVO_RECUPERACION_P20.md) y
[procedimiento C](../produccion/p20/PROCEDIMIENTO_P20_ESCENARIO_C.md).
Dominios nuevos, HTTPS de navegador y login no fueron requisitos de estos ensayos.

## Evidencia operativa

Los incidentes corregidos, simulacros y resultados de integraciones están en
el [runbook](../operacion/RUNBOOK_OPERATIVO.md): SNS (sección 1), Zoho/reintentos
(2 y 9), carga (3), autoscaling observado (4), ECS (5), RDS (6) y SES (8).
El [registro de cierres](../produccion/PENDIENTES_PRODUCCION.md#cierres)
identifica qué salió del backlog sin duplicar esos relatos.

## Decisiones de operación vigentes

- El despliegue CDK sigue siendo manual por decisión del 2026-09-29.
- Se prepara producción con listas deshabilitadas hasta contratar proveedor;
  las condiciones de activación están en la [integración](../integraciones/integracion_tusdatos_swagger.md).
- La aceptación operativa del riesgo Outlook fue registrada el 2026-10-06.
  El registro formal y su seguimiento se gestionan en [P02](../produccion/PENDIENTES_PRODUCCION.md#p02).

Este documento cambia cuando una nueva evidencia modifica el estado de un
ambiente. La prioridad y el cierre de tareas se actualizan en el backlog.
