# Pendientes de producción

Lista única de tareas de SAGRILAFT. Cada tarea tiene un código (P01, P02…) que no
cambia; los demás documentos enlazan ese código en vez de copiar su estado.

- **Estado actual de los ambientes:** [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).
- **Cómo se hace algo:** [guía de despliegue](despliegue/GUIA_DESPLIEGUE_LOCAL.md) o [runbook](../operacion/RUNBOOK_OPERATIVO.md).
- **Valores de configuración:** [Configuración en AWS](configuracion/MATRIZ_AWS_CONFIG.md).

Revisado el 2026-11-23: P01, P04, P05, P06, P07, P11, P12, P15 y P21 se contrastaron
ese día con AWS, git y GitHub. El resto conserva la fecha de su última revisión. La
evidencia que ya no existe y su fuente alternativa están en el
[índice de evidencia](../evidencia/README.md#no-conservada).

Para cerrar una tarea: anotar fecha, ambiente y evidencia, cambiar su estado y dejar
su código (no se renumera).

<a id="corte"></a>
## 1. Corte productivo

<a id="p01"></a>
### P01 — Release y trazabilidad

**Estado:** 🟡 Parcial: las releases se hacen y se verifican; falta marcar cada versión con un tag y sus notas.

Publicador SHA/manifiesto y protección de concurrencia implementados; ECR staging
inmutable. El intento 3 del 6–7 de octubre para SHA
`6542326a67d664847b3ff99bd8ec3c82ca3a7c6b` completó migración c7→f8,
activación y verificación de las cuatro imágenes/digests, cierre manual y
liberación condicional del lock ([evidencia no conservada](../evidencia/README.md#release-staging-6542326)).
El E2E anterior del 5–6 de octubre no se reasigna retroactivamente a ese SHA;
el intento 3 conserva su aceptación manual sin capturas independientes.
Falta fijar la release productiva, verificar sus imágenes/configuración y registrar
tag/notas finales. No repetir publicación o ensayo staging ya completados.

**Actualización 2026-11-23 (verificado en ECS, `/health` y git).** Ya hay releases productivas;
la vigente es `972f993`. El historial y la evidencia de cada una están en
[Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md#producción).

**Pendiente:** crear el tag de versión (`vX.Y.Z`) sobre el SHA que se apruebe en el Go (hoy
`972f993`) y sus notas en un `CHANGELOG.md`, que todavía no existe, según la
[guía](despliegue/GUIA_DESPLIEGUE_LOCAL.md#release). El repositorio no tiene ningún tag
(verificado el 2026-11-23).

<a id="p02"></a>
### P02 — Go/No-Go y riesgo de correo

**Estado:** 🟡 Parcial; Go de inicio reportado, bootstrap completado; Go final de apertura pendiente.

El [registro P02 de Go/No-Go y rollback](despliegue/P02_GO_NO_GO_ROLLBACK.md) documenta responsables, riesgo Outlook/Hotmail aceptado y su seguimiento, criterios de decisión, autoridad de rollback y procedimiento con límites posteriores a migración. El [runbook de correo](../operacion/RUNBOOK_OPERATIVO.md#ses) conserva la evidencia técnica histórica.

La autoridad final de Go/No-Go y de autorización de rollback es Andrés Hurtado. Bryan Ariza es responsable técnico de ejecución y ejecuta el rollback solo después de su autorización. El 2026-10-06 el solicitante informó que Andrés dio formalmente el Go de P02 para iniciar el corte; queda registrado como prerrequisito de aprobación cumplido para preparar el bootstrap. Esa confirmación no autorizaba por sí sola CloudFormation; el bootstrap se ejecutó después bajo su propia autorización y tiene evidencia del 7 de octubre (P04). Tampoco equivale al Go final para abrir usuarios, que requiere revisar la evidencia productiva y los criterios aplicables de P05/P06/P07. Los riesgos de correo y RDS aceptados no sustituyen esas verificaciones. La recuperación productiva todavía no ha sido ensayada; un rollback de imágenes no revierte una migración de base de datos ni recupera datos.

<a id="p03"></a>
### P03 — Configuración productiva

**Estado:** 🟡 Parcial.

Estado de credenciales verificado el 2026-10-16 comparando solo igualdad, sin imprimir valores (situación **previa** a la reconciliación del 2026-10-20 descrita más abajo):

- `zoho_credentials`: cargado el 2026-09-24 (cuenta oficial de Legal). Sus cuatro campos **no coinciden** con `.env.prod`.
- `smtp_credentials`: escrito el 2026-10-07 a las 09:05. El usuario coincide con una clave IAM **activa** de `sagrilaft-ses-smtpp`. `SMTP_USER` y `SMTP_PASSWORD` de `.env.prod` **no coinciden**.
- `db_credentials`: generado por CDK y asociado a RDS el 2026-10-07 a las 08:13. El usuario coincide con RDS. Las claves `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD` se eliminaron de `.env.prod` el 2026-10-19 porque ningún script local las lee; la fuente vigente es AWS. Producción no tiene más versiones que las de esa fecha.
- `db_credentials` de staging: no sigue el mismo historial. Dos ediciones manuales (2026-08-18 y 2026-10-28) reemplazaron el JSON que escribió el attachment y cambiaron la contraseña en Secrets Manager y en RDS. Hoy las dos coinciden y la conexión funciona. No afecta a producción, pero conviene registrar el motivo de la edición del 2026-08-18. Detalle en [MATRIZ_AWS_CONFIG.md](configuracion/MATRIZ_AWS_CONFIG.md).

Además, el 2026-10-19 se eliminaron de `.env.prod` las claves `SECRET_KEY`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD`: ningún script local las leía y sus valores viven solo en AWS (`app_secret`, `keycloak_admin`, `db_credentials`). La sincronización con `sync_aws_runtime_assets.py --apply` estuvo bloqueada por la [condición de bloqueo](despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod) hasta el 2026-10-20, cuando se concilió Zoho y SMTP (ver cierres abajo).

**Cierre SMTP (2026-10-20).** La credencial SMTP de `.env.prod` quedó identificada
(`ses-smtp-prod-sagrilaft`) y reconciliada con el secreto `sagrilaft/prod/smtp_credentials`
en AWS. Login y envío real fueron probados exitosamente. Esta parte de P03 queda resuelta.

**Cierre Zoho (2026-10-20).** Se confirmó en la consola de Zoho (Self Client) que AWS tiene
la credencial correcta (cuenta oficial de Legal); `.env.prod` tenía la cuenta operativa
anterior. Se corrigieron `.env.prod` y `.env.staging` para coincidir con
`sagrilaft/prod/zoho_credentials` y `sagrilaft/staging/zoho_credentials` respectivamente
(verificado por hash, campo a campo). Los webhooks `Sagrilaft-Produccion` y
`Sagrilaft-Staging`, que se habían borrado de Zoho Sign, se recrearon con firma HMAC.

Con esto, **P03 queda resuelto para SMTP y Zoho** — las dos condiciones que bloqueaban
`sync_aws_runtime_assets.py --apply` ([detalle](despliegue/CHECKLIST_CORTE_PRODUCCION.md#bloqueo-env-prod)).
La firma real en staging con el webhook recreado ya se probó y quedó confirmada
(`200`, expediente `SAG-9C58BEF6` pasó a `FIRMADO`). Detalle en
[runbook, sección Zoho](../operacion/RUNBOOK_OPERATIVO.md#zoho).

Misma prueba destapó un bug aparte en el portal interno (el banner de firma no se
actualizaba sin recargar); corregido y ya desplegado en staging con la release
`767b3acdc36044869d07980210e2ff212311474e`, confirmado con la misma firma real.

**Separación de credenciales SMTP por ambiente (confirmado 2026-10-20).** Local y staging
comparten la misma credencial (usuario IAM `sagrilaft-ses-smtppp`, fuente vigente en
`sagrilaft/staging/smtp_credentials`). Producción usa una credencial exclusiva y distinta
(`ses-smtp-prod-sagrilaft`, fuente vigente en `sagrilaft/prod/smtp_credentials`). Un tercer
usuario, `sagrilaft-ses-smtpp` (doble "p"), no está confirmado en uso por ningún ambiente;
no se elimina hasta confirmarlo.

**Cierre de la Fase 2 del corte, sin `--apply` (2026-10-21).** Con el SHA `6897920dec80b02171c83e3446d8f6afce14512d` y árbol limpio, cuenta `874641912777` y región `us-east-1`, se ejecutó solo lectura:
- Instantánea previa de producción (`audit_aws_secrets_safe.py`): los tres secretos de CDK (`app_secret`, `keycloak_admin`, `db_credentials`) conservan su fecha de la línea base (2026-10-07). `zoho_credentials` conserva 2026-09-24 y `smtp_credentials` 2026-10-20 13:41, el cambio registrado arriba. `sagrilaft_listas_cautela_credentials` tiene `api_key` vacía, sin uso con el proveedor deshabilitado.
- Dry-run de `sync_aws_runtime_assets.py`: sin `ERROR`; Zoho (cuatro campos) y SMTP (dos campos) figuran como "se actualizaría", listas de cautela como omitido, los tres secretos de CDK como no escritos y los cuatro repositorios ECR como existentes.
- Coherencia de valores: los seis campos de `.env.prod` (cuatro de Zoho y dos de SMTP) coinciden con AWS por huella SHA-256 (comparación de igualdad, sin imprimir valores).

**Decisión: no ejecutar `--apply`.** Escribiría exactamente los mismos valores que ya tiene AWS, solo cambiaría la fecha de versión de dos secretos y añadiría una escritura sin beneficio. Esto es coherente con el diseño verificado el mismo día: CDK no lee `.env.prod`; las tareas ECS reciben los secretos por referencia a Secrets Manager (la plantilla desplegada no contiene ninguna variable sensible en claro); `db_credentials`, `app_secret` y `keycloak_admin` los genera CDK una vez; `zoho_credentials` se importa (`zohoSecretYaExiste=true`) y CloudFormation no lo gestiona; `smtp_credentials` y `listas_cautela` los crea CDK con un valor vacío fijo, que CloudFormation solo reescribiría si ese valor cambiara en el código (dos despliegues del 2026-10-21 no modificaron `smtp_credentials`) y que el preflight rechazaría como "Cambio ajeno a la release".

Riesgos conocidos, sin cambios de código: el valor vacío fijo de `smtp_credentials` y `listas_cautela` es una trampa si alguien lo edita; los cinco secretos de CDK tienen `DeletionPolicy` y `UpdateReplacePolicy` en `Delete`; `zohoSecretYaExiste=true` debe pasarse siempre en `diff` y `deploy`.

Evidencia (fuera del repositorio, sin valores): `~/evidencia-secretos-prod-6897920dec80b02171c83e3446d8f6afce14512d/antes.json` y `dry-run.txt`.

Pendiente técnico: verificar S3/SSM, DNS/TLS, Keycloak y Bedrock desde ECS. Cierre: resultados productivos archivados sin secretos. Consultar [valores](configuracion/MATRIZ_AWS_CONFIG.md) y [contrato de configuración](configuracion/MATRIZ_AWS_CONFIG.md).

<a id="p04"></a>
### P04 — Primer despliegue productivo

**Estado:** 🟢 Hecho. El tag y las notas de la versión se siguen en [P01](#p01).

Resumen (detalle en la evidencia enlazada):
- **Bootstrap (2026-10-07):** `SagrilaftStack-prod` creado con el commit `4f7543123adea6a7da9ebbde187760a930fb1b4e` y los servicios en 0 ([evidencia no conservada](../evidencia/README.md#bootstrap-prod-20261007)).
- **Primer corte (2026-10-21, `f8d9dcf06dcfee43d6b885827444ffcee9f2007b`):** antes se resolvieron dos bloqueos del preflight de producción (tildes en la plantilla que devuelve AWS y falta de un `smoke_command` automático; fusionados en `6897920`). Migración de `[]` a `f8a9b0c1d2e3` y activación de los 4 servicios verificadas. El cliente `cdk deploy` falló por red (`ECONNRESET`) después de que CloudFormation terminara, así que la verificación se hizo a mano (12/12) y el lock quedó tomado. [Evidencia del primer corte](../evidencia/primer-corte-prod-20261021/README.md).
- **Lock liberado (2026-10-24):** verificación manual sin inconsistencias y borrado condicional por ETag. [Registro](../evidencia/primer-corte-prod-20261021/lock-reconciliation-20261024.json).
- **Verificación desde el contenedor `backend` (2026-10-27):** con el rol de la tarea responden DNS/TLS, SSM, S3 y Bedrock. Bedrock no respondió en el primer intento y luego respondió en 0,82 s dos veces; no es un bloqueante.
- **Releases posteriores:** cuatro más, la última `972f993` el 2026-11-23, con el lock libre (verificado ese día). Historial en [P01](#p01) y en [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md#producción).

 El repositorio no tiene ningún tag (verificado el 2026-11-23).

<a id="p05"></a>
### P05 — Firma automática en producción

**Estado:** 🟡 Parcial.

Cuenta/OAuth/webhook preparados y probados en staging. Falta un expediente productivo firmado que el webhook complete sin consulta manual, con PDF en S3 y auditoría. Cierra el criterio 2 del Go/No-Go referido. Procedimiento y antecedentes: [runbook, sección 9](../operacion/RUNBOOK_OPERATIVO.md#zoho).

**Bloqueo verificado el 2026-11-23: la cuenta de Zoho Sign no tiene créditos de API.** El único
intento de firma en producción (2026-11-03, 17:09 UTC) fue rechazado por Zoho con
`code 12000` («Compre créditos de Zoho Sign para enviar documentos a través de la API»). Desde
entonces no hubo más intentos ni llamadas al webhook de producción (registros del backend). Ese
intento probablemente dejó un borrador en Zoho ([P16](#p16)). No se pudo consultar el saldo actual
de créditos: hay que revisarlo en la consola de Zoho.

<a id="p06"></a>
### P06 — Alarma productiva de extremo a extremo

**Estado:** 🟡 Parcial.

El 2026-10-07 se ejecutó una prueba controlada de la acción de la alarma 5xx: se forzó temporalmente `ALARM`, CloudWatch publicó a SNS, el operador confirmó la recepción del aviso `ALARM` y de recuperación `OK`, y la suscripción temporal se eliminó. La alarma quedó en `OK`. No se activó ECS, no se publicaron imágenes ni se ejecutaron migraciones. La prueba valida la ruta de acción CloudWatch→SNS→correo, pero no la evaluación del umbral desde métricas reales. La verificación posterior confirmó que las once suscripciones definitivas seguían en `PendingConfirmation`; ninguna recibió la prueba.

**Actualización 2026-10-21 (estado real, sin cambios en AWS fuera del despliegue descrito):**
- `SagrilaftStack-prod` se actualizó con 12 correos en `snsAlertasSub`. La única suscripción nueva es `Bryan.Ariza@blend360.com`, **confirmada** en SNS. Las alarmas de producción están en `OK`.
- **Drift:** CloudFormation conserva las once suscripciones originales, pero SNS no tiene ninguna. Probablemente caducaron sin confirmar. Un despliegue no las recrea.
- **Decisión del 2026-10-21 (responsable técnico):** mientras no se autorice a los otros once, la lista de alertas de producción es solo `Bryan.Ariza@blend360.com`, tanto en SNS como en SES. No se crean suscripciones ni se envían invitaciones a los once. **Aplicada el 2026-10-21 (alineación completada):** `cdk deploy` con `snsAlertasSub=Bryan.Ariza@blend360.com` y el diff revisado (11 `destroy` de suscripciones y el cambio del parámetro SSM, sin otros recursos). Resultado: `UPDATE_COMPLETE`, los 11 recursos en `DELETE_COMPLETE` (CloudFormation respondió "Resource does not exist" y lo trató como eliminación correcta, sin `DELETE_FAILED`), un solo recurso de suscripción en el stack, SNS solo con `Bryan.Ariza@blend360.com` y `ALERTAS_EMAIL_DESTINATARIO` en versión 3 con ese único correo. Los cuatro servicios ECS siguen en 0/0/0 y las alarmas en `OK`. Sin cambios de código; las 26 pruebas de infraestructura pasan. [Evidencia](../evidencia/sns-alertas-prod-20261021/README.md).
- **Pendiente, sin autorización:** los once destinatarios originales quedan fuera de la lista vigente. Reincorporarlos requiere autorización explícita, volver a ponerlos en `snsAlertasSub` y confirmar cada invitación.
- **Límite que ya se levantó:** las alarmas de servidor y CPU/memoria dependían de métricas del servicio ECS, que estaba en `desiredCount=0`. **Los 4 servicios están activos desde el 2026-10-21** ([P04](#p04)), así que ya pueden generar métricas reales.

**Qué falta para cerrar P06:**
1. ~~Alinear el drift~~ (hecho el 2026-10-21). Cuando se autorice a los otros once, reincorporarlos en `snsAlertasSub`, redesplegar y confirmar cada invitación; P06 no cierra sin ellos.
2. ~~Activar los servicios ECS~~ (hecho el 2026-10-21, ver [P04](#p04)).
3. Provocar una alarma por métrica real con los servicios activos y verificar que el aviso llegue a la lista definitiva (hoy, solo `Bryan.Ariza@blend360.com`) en menos de cinco minutos. Pendiente de ejecutar.
4. Registrar cada paso en la evidencia de la fecha correspondiente.

**Actualización 2026-11-23 (verificado en CloudWatch y SNS).** Producción pasó de 3 a 16 alarmas;
todas estaban en `OK` ese día y avisan por SNS al fallar y al recuperarse. La lista y qué hacer
con cada una están en el [runbook](../operacion/RUNBOOK_OPERATIVO.md#que-hacer-alarma). El tema
sigue con una sola suscripción de correo confirmada. Los puntos 1 (destinatarios) y 3 (prueba con
una métrica real) siguen pendientes.

[Evidencia de la actualización de hoy](../evidencia/sns-alertas-prod-20261021/README.md). [Evidencia de la prueba temporal](../evidencia/README.md#sns-prueba-temporal-20261007) (no conservada). [Procedimiento](../operacion/RUNBOOK_OPERATIVO.md#alarmas). [Evidencia de creación](../evidencia/README.md#bootstrap-prod-20261007) (no conservada).

<a id="p07"></a>
### P07 — Smoke funcional y correo productivos

**Estado:** 🔴 Pendiente.

Crear un acceso real, recibir el correo y recorrer guardado, adjuntos/IA, descarga S3, radicación, revisión y cierre; verificar autenticación/roles y ausencia de errores. Reutilizar el [recorrido E2E](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md) como referencia y archivar una ejecución separada de producción. Firma y alarma se cierran en P05/P06, sin repetir tareas.

**Prerrequisito de usuarios (2026-10-21, cumplido el 2026-10-27):** el realm de Keycloak importado no trae ningún usuario (solo el cliente `sagrilaft-portal` y los roles `acceso_clientes`/`acceso_proveedores`), así que había que crearlos a mano desde la consola de administración de producción. **El 2026-10-27 el responsable técnico informó que los usuarios internos ya están creados en producción**, configurados a mano en lugar de importarlos desde staging (el export parcial de la consola no incluye usuarios). **Revisión de inventario (2026-10-27, en la consola de producción de Keycloak, solo lectura):** el realm `sagrilaft` tiene los usuarios internos esperados y los roles y grupos de acceso están configurados. No se modificó ningún usuario, grupo ni asignación. Los correos y nombres de usuario no se registran en este documento. El código lee roles de realm desde `realm_access.roles` ([autenticacion.py](../../backend/api/middleware/autenticacion.py#L212)), así que el acceso depende de que los grupos aporten esos roles al token. **Verificado el 2026-10-27 (Fase 2, pasos 1 y 2):** con la herramienta de evaluación de tokens de Keycloak, un usuario de cada grupo recibe en `realm_access.roles` exactamente el rol de su membresía. **Pendiente en staging:** alinear el secreto de administración de Keycloak con su valor real. Con los usuarios y roles verificados, P07 ya puede ejecutarse.

**Antes de ejecutar P07 (2026-11-23):** el bucket de producción ya tiene archivos de pruebas
anteriores; decidir qué hacer con ellos en [P21](#p21) para no mezclar la ejecución de P07 con esos datos.

<a id="p08"></a>
### P08 — Observación HSTS

**Estado:** 🟢 Verificado en producción (2026-10-21).

Staging reportó HSTS desactivado; esa observación ya no se reproduce (se confirmó HSTS presente en los tres dominios de staging al probar `smoke_readonly.py`). El bootstrap productivo aplicó en el listener HTTPS del ALB `Strict-Transport-Security: max-age=31536000`. Tras activar los 4 servicios, el smoke externo manual confirmó, en los tres dominios de producción: redirección HTTP→HTTPS, respuesta HTTPS correcta y encabezado HSTS presente. [Evidencia](../evidencia/primer-corte-prod-20261021/README.md). [Bootstrap de producción](../evidencia/README.md#bootstrap-prod-20261007) (no conservada). [Observación original en staging](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md).

**Hallazgo relacionado (2026-10-24), exposición de la consola admin de Keycloak.** La URL
`https://login-sagrilaft.ia.blend360.com/admin/master/console/` es alcanzable desde internet. TLS y HSTS
son correctos; el riesgo es de fuerza bruta contra el usuario administrador. Estado:
- **Protección de fuerza bruta en Keycloak:** configurada manualmente por el responsable técnico en los realms
  `master` y `sagrilaft` (máx. 5 fallos, espera 1 min con tope de 15, reinicio a las 12 h, bloqueo permanente
  desactivado). **Reportada, no verificada por el asistente:** no hay configuración de esta protección en el
  repositorio (el realm importado no la define), así que un reimport del realm la sobrescribiría. Pendiente
  exportar la configuración a un archivo controlado o documentar su reaplicación.
- **WAF, regla `LimiteTasaAdminKeycloak`** (`infra/sagrilaft/lib/constructs/cortafuegos-web.ts`, prioridad 4):
  200 peticiones por IP en 5 min para `/admin` y `/realms/master`. Cambio aplicado en el código y con
  6 pruebas nuevas; 32 pruebas de infraestructura pasan. `cdk diff` de producción: solo cambia el WebACL
  (regla añadida). **Desplegada en staging el 2026-10-24** (`cdk deploy` con los valores reales de staging:
  imagen `767b3ac…`, NAT apagado, `zohoSecretYaExiste=false`; solo cambió el WebACL). **Bloqueo verificado en
  staging:** tras bajar el límite a 10 para la prueba, las peticiones a `/admin` recibieron `403` y el WAF
  registró `BlockedRequests` y muestras `BLOCK` con la IP de origen. Las primeras pruebas con límite 200 no
  mostraron bloqueo porque la evaluación de la ventana deslizante del WAF tarda en acumular el conteo. El
  límite se restauró a 200 y se verificó en AWS; portal y formulario de staging sin cambios.
  **Desplegada en producción el 2026-10-24** (`cdk deploy` con los mismos argumentos del diff revisado; solo
  cambió el WebACL, `UPDATE_COMPLETE`). Regla verificada en vivo (prioridad 4, límite 200, acción `Block`).
  Servicios ECS sin cambios (`desired=1 running=1`); formulario, portal y consola admin responden `200` con
  tráfico normal. No se forzó bloqueo en producción: el mecanismo ya quedó verificado en staging.
  **P08 completo** (HSTS verificado y exposición de la consola admin mitigada).

## 2. Operación posterior

<a id="p09"></a>
### P09 — Evento real de autoscaling

**Estado:** 🟡 Parcial; futuro, no bloqueante.

Carga de staging terminada; no se observó scale-out. Observarlo con carga distribuida o en un pico real y registrar métricas/tareas. No reabrir la carga ya realizada. [Runbook, sección 4](../operacion/RUNBOOK_OPERATIVO.md#autoscaling).

<a id="p10"></a>
### P10 — Restauración y RTO de producción

**Estado:** 🟡 Parcial; cuando exista producción.

Para el primer corte se aceptó el riesgo de RDS descrito en [P02](despliegue/P02_GO_NO_GO_ROLLBACK.md#riesgo-rds-aceptado-para-el-primer-corte). Esa aceptación no cierra P10: resta restaurar un backup productivo a una instancia temporal separada, verificar integridad, medir RTO y eliminar solo la copia temporal. [Procedimiento y referencia de staging](../operacion/RUNBOOK_OPERATIVO.md#restauracion).


## 3. Mejoras y verificaciones externas

<a id="p11"></a>
### P11 — OIDC y build/push automático

**Estado:** 🟡 Parcial; OIDC configurado y funcionando, pero con un riesgo de seguridad abierto en el rol.

**Verificado el 2026-10-28:** la variable `AWS_ROLE_TO_ASSUME` existe y apunta a un rol de despliegue por OIDC (configurada 2026-10-21) y el proveedor OIDC de GitHub existe en la cuenta (`token.actions.githubusercontent.com`). El workflow de build/push ya corre con esto, sin llaves estáticas.

**Hallazgo de seguridad (2026-10-28):** el rol de despliegue OIDC es genérico y compartido con otros repositorios de la organización, no dedicado a este proyecto. Su confianza es más amplia de lo necesario y tiene permisos de administración de servicios que este proyecto no usa. El riesgo es que un workflow de otro repositorio lo asuma con permisos excesivos.

**Pendiente de corrección:** crear un rol dedicado a SAGRILAFT, con confianza limitada a este repositorio y permisos mínimos para publicar imágenes, y migrar `AWS_ROLE_TO_ASSUME` a ese rol. No bloquea el deploy manual, pero es una brecha de seguridad real en la cuenta compartida. [Workflow](../../.github/workflows/ci.yml).

**CI en rojo (verificado el 2026-11-23).** Las últimas seis ejecuciones del workflow en `main`
(18 y 23 de noviembre) fallan en «Publish immutable SHA images» con «AWS ssm/get-parameters
falló»: el rol no tiene ese permiso. Las pruebas del backend y gitleaks pasan. No afecta a los
despliegues, que son manuales, pero el rojo constante oculta fallos reales. Se corrige con el rol
dedicado de este punto o desactivando la publicación automática. Ya existe una propuesta del
permiso mínimo de lectura de SSM para el CI:
[`infra/sagrilaft/policies/github-build-ssm.template.json`](../../infra/sagrilaft/policies/github-build-ssm.template.json)
(hay que sustituir sus marcadores y revisar límites y políticas antes de aplicarla).

<a id="p12"></a>
### P12 — Protección de main

**Estado:** 🔴 Confirmado sin protección (2026-10-28; vuelto a verificar el 2026-11-23: `branches/main/protection` responde 404 y no hay rulesets).

`GET branches/main/protection` y `GET rulesets` devuelven 404 / lista vacía: **`main` no tiene ninguna regla de protección**, ni clásica ni por ruleset.
**Pendiente:** un administrador del repositorio debe activar branch protection en `main` exigiendo PR + al menos 1 revisión y el check `Run Backend Tests` en verde antes de mergear. Hasta entonces, los cambios pueden llegar a `main` sin revisión.

<a id="p13"></a>
### P13 — Ejecución fiable de CDK Diff

**Estado:** 🟡 Implementado; ejecución no acreditada.

El [workflow](../../.github/workflows/cdk-diff.yml) existe (commit `ef56a8a`, 2026-10-06). Acreditar ejecución con OIDC (P11) y revisar que `|| true` no oculte errores. No queda pendiente crear el job.

<a id="p14"></a>
### P14 — Caso de uso SES ante AWS

**Estado:** 🔴 Abierto en el registro; no bloqueante técnico.

Se registraron WebsiteURL/UseCaseDescription de otro proyecto y ticket interno al administrador de la cuenta compartida. Actualizar el caso y conservar confirmación de cierre. [Hallazgo](../operacion/RUNBOOK_OPERATIVO.md#ses).

<a id="p15"></a>
### P15 — Activación futura de listas

**Estado:** 🔴 Diferido; no bloquea el corte acordado.

Contratar proveedor, obtener URL/credenciales y validar integración real cuando se active. La decisión de arrancar deshabilitado ya está tomada; no equivale a contratarlo. Trabajo pendiente en [Operación del módulo de listas](../listas/OPERACION_PRUEBAS_Y_PENDIENTES.md#proveedor-externo).

**Actualización 2026-11-23 (verificado en el código y en AWS).** El texto anterior decía que no
había adaptador externo; eso ya no es cierto. El adaptador de Tusdatos existe
(`backend/infrastructure/listas/tusdatos/`) y está desplegado desde `d4cdb84` (2026-11-18). Activarlo
todavía requiere tres cosas: el contrato; credenciales reales (el secreto
`sagrilaft/prod/tusdatos_credentials` existe con sus tres campos vacíos); y un cambio de código,
porque `configuracion.py` rechaza en producción cualquier proveedor distinto de `deshabilitado`. En
producción, `PROVEEDOR_LISTAS_CAUTELA=deshabilitado` y el trabajador de listas está en 0 tareas.

**Pendiente de confirmar:** si existe la aprobación de Cumplimiento para operar temporalmente sin proveedor de listas. La plantilla local refleja `deshabilitado`; no modifica la configuración efectiva de producción.

<a id="p16"></a>
### P16 — Borradores Zoho huérfanos

**Estado:** 🔴 Limitación aceptada de bajo impacto.

Cuando la creación remota funciona y submit falla, el request_id no se conserva para cancelar. Resolver compensación/seguimiento y probar ese fallo cuando se priorice. [Limitación documentada](../operacion/RUNBOOK_OPERATIVO.md#huerfanos).

<a id="p17"></a>
### P17 — Ampliación de documentación técnica

**Estado:** 🔴 Mejora no bloqueante.

Ampliar modelo de datos (JSON/auditoría), contrato HTTP/Pydantic y arquitectura React/Keycloak/Axios. Publicar cada detalle en su documento técnico, sin añadir estados de despliegue o listas de tareas allí.

<a id="p18"></a>
### P18 — Evidencia complementaria

**Estado:** ⚪ Sin evidencia suficiente.

Acreditar invalidación de todos los accesos de prueba. La desaparición de alertas de consistencia está declarada, sin captura independiente: obtenerla si se exige. Para distribución externa, generar copias anonimizadas; el E2E registra datos sensibles residuales en imágenes/PDF. No alterar los originales. [Registro](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md).

<a id="p19"></a>
### P19 — Cobertura automática y PostgreSQL en CI

**Estado:** 🟡 Parcial; mejora de cobertura.

Automatizar los huecos enumerados en el [catálogo frontend](../../tests/README.md#cobertura), ejecutar migraciones/flujo PostgreSQL en CI y acreditar su resultado. La cobertura local ya se amplió a 28 revisiones y operaciones de repositorios sobre PG16.6 (44 passed / 3 xfailed históricos); no repetir esa ampliación como pendiente. Alcance en el harness. El [README del harness](../../tests/integration/README.md) define comandos/variables. Una prueba manual de staging no sustituye regresiones automáticas.

<a id="p21"></a>
### P21 — Datos de prueba en producción

**Estado:** 🔴 Requiere decisión antes de abrir (registrado el 2026-11-23).

El bucket de documentos de producción tiene 29 objetos de pruebas hechas en producción (subidos
el 30 y 31 de octubre, el 3 de noviembre y el 18 de noviembre), en carpetas de clientes y
proveedores; una de ellas lleva el nombre de una empresa. No se revisó el contenido de la base de
datos ni de los archivos. La copia `sagrilaft-prod-base-pre-pruebas-20261123` se tomó el
2026-11-23, después de esas pruebas, así que también los contiene: no es una base limpia.

Decidir, antes de P07 y de la apertura:
1. Si son datos ficticios o de personas o empresas reales (en ese caso, también es un tema de protección de datos).
2. Si se limpian, con un procedimiento que trate base de datos y S3 juntos (la auditoría limita los borrados), o si se conservan marcados como prueba.

No hay procedimiento de limpieza escrito; crearlo es parte de este pendiente.

<a id="cierres"></a>
## 4. Cierres y decisiones — fuera del backlog activo

Esta tabla sustituye los relatos duplicados. Los detalles originales permanecen
en la evidencia enlazada. Un cierre solo cubre el alcance indicado.

| Cierre / decisión | Fecha / alcance | Fuente de evidencia |
|---|---|---|
| ECR staging inmutable | 6 octubre, 15:54:14 Bogotá; cuatro repositorios, solo mutabilidad, stack UPDATE_COMPLETE | Informe no archivado en el repositorio; ver [evidencia de la release](../evidencia/README.md#release-staging-6542326) (no conservada) |
| Puesta en marcha de staging y migración ECS | Registro previo; staging | [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md) |
| Flujo completo, firma, auditoría y cierre | 5–6 octubre; AWS staging | [E2E](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md), [PDF](../evidencia/e2e-staging/auditoria_74d14aad.pdf) |
| Carga v1/v2 y fix de concurrencia S3 | 21–22 septiembre; 0 errores 500/2207 requests en v2 | [Runbook, sección 3](../operacion/RUNBOOK_OPERATIVO.md#carga) |
| Circuit Breaker / healthCheckGracePeriod | 21 septiembre; deploy staging exitoso | [Runbook, sección 5](../operacion/RUNBOOK_OPERATIVO.md#ecs) |
| Restauración RDS staging | 19 septiembre; RTO observado 10–15 min | [Runbook, sección 6](../operacion/RUNBOOK_OPERATIVO.md#restauracion) |
| SNS→correo staging | 19 septiembre | [Runbook, sección 1](../operacion/RUNBOOK_OPERATIVO.md#alarmas) |
| Manejo de reintentos Zoho | 22 septiembre; 8 tests nuevos, registro 97 passed/1 skipped | [Runbook, sección 2](../operacion/RUNBOOK_OPERATIVO.md#reintentos) |
| Cuenta oficial, secreto productivo y webhook Zoho; HMAC/casing e idempotencia | 24 septiembre; preparado prod, probado staging | [Runbook, sección 9](../operacion/RUNBOOK_OPERATIVO.md#zoho) |
| SES fuera de sandbox, remitente y DKIM | 23 septiembre | [Runbook, sección 8](../operacion/RUNBOOK_OPERATIVO.md#ses) |
| NAT productiva en scripts e importación de secreto Zoho | Implementación; no despliegue prod | [Runbook, sección 9](../operacion/RUNBOOK_OPERATIVO.md#zoho) |
| Apagado NAT temporal staging | 28 septiembre registrado; repetido tras E2E octubre; repetido el 20 de octubre tras validar el webhook recreado | [Paso I E2E](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md); [runbook, sección Zoho](../operacion/RUNBOOK_OPERATIVO.md#zoho) |
| Variante PostgreSQL y migraciones desde cero | 1 octubre; migraciones 2/2 y flujo 12/12 | [Validación local](../evidencia/e2e-staging/VALIDACION_STAGING_E2E.md) |
| Gate backend en CI | 19 septiembre; `needs: test`, PR/main y publicación solo push | [Workflow](../../.github/workflows/ci.yml) |
| Crear CDK Diff | 6 octubre; commit `ef56a8a` | [Workflow](../../.github/workflows/cdk-diff.yml); ejecución en P13 |
| Destinatarios de alarmas incluidos en comandos CDK | 29 septiembre; corrección documental | [Contexto de corte](despliegue/CHECKLIST_CORTE_PRODUCCION.md#contexto); aplicación y recepción en P06 |
| SECRET_KEY local no requiere migración manual | CDK genera app_secret; ECS lo consume | [Matriz](configuracion/MATRIZ_AWS_CONFIG.md) |
| Deploy manual y listas deshabilitadas | Decisiones del 29 septiembre | [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md) |
| Definición Go/No-Go y rollback reportada | 27–28 septiembre; se reportaron 8 criterios y 4 escenarios, sin aprobación acreditada. Registro local revisado el 6 de octubre | [Registro P02](despliegue/P02_GO_NO_GO_ROLLBACK.md); el artefacto externo referido no pudo verificarse |
| Volumen y límite acordados con negocio | 27 septiembre; ~100 contrapartes/mes y 60/min | Registro de decisión conservado de la documentación previa; relacionado con [carga](../operacion/RUNBOOK_OPERATIVO.md#carga) |
| Manuales y runbook escritos | Cierre documental al 6 octubre | [Contraparte](../manuales/MANUAL_USUARIO_CONTRAPARTE.md), [portal](../manuales/MANUAL_USUARIO_PORTAL_INTERNO.md), [runbook](../operacion/RUNBOOK_OPERATIVO.md) |
| Preparación local de .env.prod | 6 octubre; presencia de campos sin exponer valores | Revisión local registrada; vigencia/carga en P03 |

## 5. Cómo mantener este registro

Para cerrar un ID: registrar fecha, ambiente y evidencia; conservar el ancla y
moverlo a cierres. Actualizar Estado solo si cambia un ambiente. Una nueva prueba
productiva se archiva separada de staging. No cerrar por existencia de código,
comandos escritos o casillas antiguas. No borrar limitaciones aceptadas.
