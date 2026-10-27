# Pendientes para producción — registro único de tareas
Evidencias originales P20: consultar el [índice del archivo P20](p20/EVIDENCIAS_P20_ARCHIVADAS.md); las rutas entre paréntesis son relativas a su contenido.

Revisión documental: 2026-10-21 (P03: SMTP/Zoho y release de staging del 20 de octubre).
Los demás pendientes conservan sus evidencias históricas (P20 y staging/bootstrap: 2026-10-16). Función única: registrar tareas, decisiones de cierre y
criterios de aceptación. Los estados externos se basan en evidencias archivadas y revalidaciones
fechadas por ejecución; esto no es una auditoría general actual de AWS/GitHub. [Mapa documental](../README.md#funciones).

Cada tarea tiene un ID estable. Los demás documentos enlazan ese ID; no mantienen
otra casilla, prioridad o estado para la misma tarea. Las instrucciones están
en checklist/guía/runbook; los valores en el catálogo por ambiente.

<a id="corte"></a>
## 1. Corte productivo

<a id="p01"></a>
### P01 — Release y trazabilidad

**Estado:** 🟡 Parcial; release coordinada de staging acreditada, release productiva pendiente.

Publicador SHA/manifiesto y protección de concurrencia implementados; ECR staging
inmutable. El intento 3 del 6–7 de octubre para SHA
`6542326a67d664847b3ff99bd8ec3c82ca3a7c6b` completó migración c7→f8,
activación y verificación de las cuatro imágenes/digests, cierre manual y
liberación condicional del lock. [Evidencias y límites en P20](#p20).
El E2E anterior del 5–6 de octubre no se reasigna retroactivamente a ese SHA;
el intento 3 conserva su aceptación manual sin capturas independientes.
Falta fijar la release productiva, verificar sus imágenes/configuración y registrar
tag/notas finales. No repetir publicación o ensayo staging ya completados.

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
- `db_credentials`: generado por CDK y asociado a RDS el 2026-10-07 a las 08:13. El usuario coincide con RDS. Las claves `KEYCLOAK_DB_USER` y `KEYCLOAK_DB_PASSWORD` se eliminaron de `.env.prod` el 2026-10-19 porque ningún script local las lee; la fuente vigente es AWS.

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
- Instantánea previa (`audit_aws_secrets_safe.py`): los tres secretos de CDK (`app_secret`, `keycloak_admin`, `db_credentials`) conservan su fecha de la línea base (2026-10-07). `zoho_credentials` conserva 2026-09-24 y `smtp_credentials` 2026-10-20 13:41, el cambio registrado arriba. `sagrilaft_listas_cautela_credentials` tiene `api_key` vacía, sin uso con el proveedor deshabilitado.
- Dry-run de `sync_aws_runtime_assets.py`: sin `ERROR`; Zoho (cuatro campos) y SMTP (dos campos) figuran como "se actualizaría", listas de cautela como omitido, los tres secretos de CDK como no escritos y los cuatro repositorios ECR como existentes.
- Coherencia de valores: los seis campos de `.env.prod` (cuatro de Zoho y dos de SMTP) coinciden con AWS por huella SHA-256 (comparación de igualdad, sin imprimir valores).

**Decisión: no ejecutar `--apply`.** Escribiría exactamente los mismos valores que ya tiene AWS, solo cambiaría la fecha de versión de dos secretos y añadiría una escritura sin beneficio. Esto es coherente con el diseño verificado el mismo día: CDK no lee `.env.prod`; las tareas ECS reciben los secretos por referencia a Secrets Manager (la plantilla desplegada no contiene ninguna variable sensible en claro); `db_credentials`, `app_secret` y `keycloak_admin` los genera CDK una vez; `zoho_credentials` se importa (`zohoSecretYaExiste=true`) y CloudFormation no lo gestiona; `smtp_credentials` y `listas_cautela` los crea CDK con un valor vacío fijo, que CloudFormation solo reescribiría si ese valor cambiara en el código (dos despliegues del 2026-10-21 no modificaron `smtp_credentials`) y que el preflight rechazaría como "Cambio ajeno a la release".

Riesgos conocidos, sin cambios de código: el valor vacío fijo de `smtp_credentials` y `listas_cautela` es una trampa si alguien lo edita; los cinco secretos de CDK tienen `DeletionPolicy` y `UpdateReplacePolicy` en `Delete`; `zohoSecretYaExiste=true` debe pasarse siempre en `diff` y `deploy`.

Evidencia (fuera del repositorio, sin valores): `~/evidencia-secretos-prod-6897920dec80b02171c83e3446d8f6afce14512d/antes.json` y `dry-run.txt`.

Pendiente técnico: verificar S3/SSM, DNS/TLS, Keycloak y Bedrock desde ECS. Cierre: resultados productivos archivados sin secretos. Consultar [valores](configuracion/checklist-valores-staging-prod.md) y [contrato de configuración](configuracion/MATRIZ_AWS_CONFIG.md).

<a id="p04"></a>
### P04 — Primer despliegue productivo

**Estado:** 🟡 Parcial; migración y activación completadas y verificadas; falta reconciliar el lock de S3 y cerrar el cierre formal.

El bootstrap base de `SagrilaftStack-prod` se completó el 2026-10-07 con el código del commit `4f7543123adea6a7da9ebbde187760a930fb1b4e`; la evidencia está en [bootstrap de producción](../evidencia/bootstrap-prod-4f7543123adea6a7da9ebbde187760a930fb1b4e/README.md). SMTP y Zoho ya están conciliados (P03, 2026-10-20) y el drift de SNS está corregido (2026-10-21, ver [P06](#p06)).

**Bloqueos del 2026-10-21, resueltos antes de publicar imágenes:**
1. **Preflight de producción.** `GetTemplate` de `SagrilaftStack-prod` devolvía `?` donde el código tiene tildes; la equivalencia `STAGING_UNICODE_PAIRS` de `deploy_release.py` solo cubría staging. **Resuelto y fusionado a `main`** (commit `5de2035`, dentro de `6897920`): ahora `APPROVED_UNICODE_PAIRS` cubre `staging` y `prod`; cualquier otro ambiente, texto o ruta sigue estricto. 52 pruebas nuevas.
2. **`smoke_command` automático.** No existía ninguno para producción (el modo manual es solo de staging). **Resuelto y fusionado**: [scripts/despliegue/smoke_readonly.py](../../scripts/despliegue/smoke_readonly.py), de solo `GET`. 48 pruebas unitarias.
3. Fase 2 (secretos): **cerrada sin `--apply`** el mismo día, ver más abajo.

**Publicación de imágenes (2026-10-21).** Las cuatro imágenes del SHA `f8d9dcf06dcfee43d6b885827444ffcee9f2007b` quedaron publicadas y verificadas en ECR (manifiesto `complete: true`, digests coincidentes, los 4 repositorios `IMMUTABLE`). Verificado también: cuenta y región, Python 3.12, Docker disponible, `.env.prod` con permisos `600`.

**Migración y activación (2026-10-21, ejecutadas con `deploy_release.py --execute`):**
- **Migración:** tarea ECS verificada con `exitCode=0`; revisión Alembic pasó de `[]` a `f8a9b0c1d2e3`, la esperada.
- **Activación:** CloudFormation terminó en `UPDATE_COMPLETE`; los 4 servicios en `ACTIVE`, `desired=1 running=1`, con los digests aprobados. Target groups del ALB, los 4 `healthy`. Smoke externo manual, 12/12 comprobaciones (HTTPS, HSTS, redirección, `/health` con commit y base de datos, OIDC de Keycloak).
- **Incidente sin impacto en AWS:** el cliente `cdk deploy` falló con `TimeoutError: read ECONNRESET` justo después de que CloudFormation completara. El orquestador se detuvo antes de sus propias verificaciones (no llegó a `services()` ni al smoke automático) y **conserva el lock de S3** sin liberar. La verificación posterior fue manual, independiente del orquestador. [Evidencia completa](../evidencia/primer-corte-prod-20261021/README.md).

**Lock de S3 reconciliado y liberado (2026-10-24).** Verificación manual previa, replicando las
mismas funciones del orquestador (`comparison_template`, `services()`): cuenta activa, stack
`UPDATE_COMPLETE` sin cambios desde la activación, plantilla desplegada idéntica a la `activate`
aprobada, los 4 servicios con digests/estado correctos, y `planHash` de `lock.json` coincidente
con el evento `plan_validated` del mismo intento. Sin inconsistencias. Borrado condicional
(`delete-object --if-match` con el ETag exacto), confirmado con `404` posterior. No existe hoy
una herramienta automática de reconciliación para producción (solo para `smoke_mode=manual`,
exclusivo de staging); se hizo a mano, con el mismo rigor. Evidencia:
`execute-1/lock-reconciliation-20261024.json` (fuera del repositorio).

**Pendiente para cerrar P04:**
1. ~~Reconciliar y liberar el lock de S3~~ (hecho el 2026-10-24).
2. Registrar el cierre formal (tag/notas de release, según la [guía](despliegue/GUIA_DESPLIEGUE_LOCAL.md#release)).
3. Verificar S3/SSM, DNS/TLS y Bedrock desde ECS (pendiente técnico de siempre, sin cambios).

<a id="p05"></a>
### P05 — Firma automática en producción

**Estado:** 🟡 Parcial.

Cuenta/OAuth/webhook preparados y probados en staging. Falta un expediente productivo firmado que el webhook complete sin consulta manual, con PDF en S3 y auditoría. Cierra el criterio 2 del Go/No-Go referido. Procedimiento y antecedentes: [runbook, sección 9](../operacion/RUNBOOK_OPERATIVO.md#zoho).

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

[Evidencia de la actualización de hoy](../evidencia/sns-alertas-prod-20261021/README.md). [Evidencia de la prueba temporal](../evidencia/sns-prueba-temporal-prod-20261007.json). [Procedimiento](../operacion/RUNBOOK_OPERATIVO.md#alarmas). [Evidencia de creación](../evidencia/bootstrap-prod-4f7543123adea6a7da9ebbde187760a930fb1b4e/README.md).

<a id="p07"></a>
### P07 — Smoke funcional y correo productivos

**Estado:** 🔴 Pendiente.

Crear un acceso real, recibir el correo y recorrer guardado, adjuntos/IA, descarga S3, radicación, revisión y cierre; verificar autenticación/roles y ausencia de errores. Reutilizar el [recorrido E2E](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md) como referencia y archivar una ejecución separada de producción. Firma y alarma se cierran en P05/P06, sin repetir tareas.

**Prerrequisito de usuarios (2026-10-21, cumplido el 2026-10-27):** el realm de Keycloak importado no trae ningún usuario (solo el cliente `sagrilaft-portal` y los roles `acceso_clientes`/`acceso_proveedores`), así que había que crearlos a mano desde la consola de administración (`https://login-sagrilaft.ia.blend360.com`). **El 2026-10-27 el responsable técnico informó que los usuarios internos ya están creados en producción**, configurados a mano en lugar de importarlos desde staging (el export parcial de la consola no incluye usuarios). *Reportado, no verificado por el asistente:* no se revisó en Keycloak cuántos usuarios hay, qué rol tiene cada uno ni si hay grupos. **Abierto:** confirmar que la contraseña del secreto `sagrilaft/prod/keycloak_admin` coincide con la que realmente entra a la consola; el 2026-10-27 en staging no coincidía (alguien la cambió directo en Keycloak sin actualizar el secreto), y en producción no se ha comprobado. Con los usuarios creados, P07 ya puede ejecutarse.

<a id="p08"></a>
### P08 — Observación HSTS

**Estado:** 🟢 Verificado en producción (2026-10-21).

Staging reportó HSTS desactivado; esa observación ya no se reproduce (se confirmó HSTS presente en los tres dominios de staging al probar `smoke_readonly.py`). El bootstrap productivo aplicó en el listener HTTPS del ALB `Strict-Transport-Security: max-age=31536000`. Tras activar los 4 servicios, el smoke externo manual confirmó, en los tres dominios de producción: redirección HTTP→HTTPS, respuesta HTTPS correcta y encabezado HSTS presente. [Evidencia](../evidencia/primer-corte-prod-20261021/README.md). [Bootstrap de producción](../evidencia/bootstrap-prod-4f7543123adea6a7da9ebbde187760a930fb1b4e/README.md). [Observación original en staging](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md).

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

**Estado:** ⚪ Estado externo actual sin confirmar; no bloquea deploy manual.

El 2026-09-29 se registró `Credentials could not be loaded` y ausencia de `AWS_ROLE_TO_ASSUME` en `gh variable list`. Comprobar rol/variable actuales, configurarlos si faltan y acreditar build/push. [Workflow](../../.github/workflows/ci.yml).

<a id="p12"></a>
### P12 — Protección de main

**Estado:** ⚪ Estado externo actual sin confirmar.

El intento registrado sobre `branches/main/protection` devolvió 404 con acceso WRITE. Comprobar si `Run Backend Tests` es obligatorio; si falta, un administrador debe aplicar la regla. Cierre: configuración de protección verificada. El gate implementado no prueba protección activa.

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

Contratar proveedor, obtener URL/credenciales y validar integración real cuando se active. La decisión de arrancar deshabilitado ya está tomada; no equivale a contratarlo. [Procedimiento de activación](../integraciones/integracion_tusdatos_swagger.md#activacion).

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

<a id="p20"></a>
### P20 — Validación del despliegue coordinado y recuperación

**Estado:** 🟡 El ensayo normal de staging está verificado; los ensayos de
recuperación aislada A, B y C están cerrados formalmente. Cada escenario tiene
evidencia, aprobación, excepción y límites propios. A comprobó los dos fallos
controlados antes de DDL; B comprobó expansión aditiva, rollback de activación
y compatibilidad GET/PUT/GET; C comprobó incompatibilidad, restauración del
snapshot a una RDS nueva y smoke aislado GET/PUT/GET con persistencia. Para C,
CloudFormation quedó `UPDATE_COMPLETE`, los cuatro servicios ECS en `0/0/0` y
el lock se liberó condicionalmente. Ver [plan operativo](p20/PLAN_OPERATIVO_RECUPERACION_P20.md)
y los procedimientos [A](p20/PROCEDIMIENTO_P20_ESCENARIO_A.md),
[B](p20/PROCEDIMIENTO_P20_ESCENARIO_B.md) y [C](p20/PROCEDIMIENTO_P20_ESCENARIO_C.md).

El cierre de A/B/C no cierra los gates del despliegue productivo. El laboratorio
se retiró el 16 de octubre de 2026: la infraestructura AWS P20 fue eliminada y la
evidencia se conserva en archivo local ([retiro](p20/RETIRO_P20.md)). Dominios
nuevos, HTTPS de navegador y login no fueron requisitos de recuperación A/B/C.

El 6–7 de octubre de 2026 se ejecutó y cerró el intento 3 del despliegue coordinado para el SHA `6542326a67d664847b3ff99bd8ec3c82ca3a7c6b`. La preparación conservó los servicios anteriores; la migración ECS terminó con `ExitCode=0` y verificó Alembic desde `c7a1c1a65662` hasta `f8a9b0c1d2e3`; luego se activaron los cuatro servicios con los digests aprobados. CloudFormation quedó en `UPDATE_COMPLETE`, ECS verificó las tareas y digests, y el lock se liberó condicionalmente después del cierre manual. Las cuatro comprobaciones manuales fueron declaradas aprobadas por el operador y quedaron asentadas sin capturas ni secretos. La evidencia del intento está en [release de staging](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/deploy-intento-3/), incluidos [eventos](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/deploy-intento-3/events.jsonl), [verificación del esquema](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/deploy-intento-3/schema-evidence.json), [servicios activos](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/deploy-intento-3/active-services.json) y [cierre manual](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/deploy-intento-3/manual-accepted.json).

La cronología detallada del laboratorio (9–14 de octubre: restauraciones, digests, repoint e incidentes) está en el [plan operativo P20](p20/PLAN_OPERATIVO_RECUPERACION_P20.md#cronología-histórica-del-laboratorio). El laboratorio se retiró el 16 de octubre; ver [retiro](p20/RETIRO_P20.md).

P04 sigue pendiente y conserva el primer corte productivo. El ensayo de staging no equivale a autorización ni ejecución en producción.

<a id="cierres"></a>
## 4. Cierres y decisiones — fuera del backlog activo

Esta tabla sustituye los relatos duplicados. Los detalles originales permanecen
en la evidencia enlazada. Un cierre solo cubre el alcance indicado.

| Cierre / decisión | Fecha / alcance | Fuente de evidencia |
|---|---|---|
| ECR staging inmutable | 6 octubre, 15:54:14 Bogotá; cuatro repositorios, solo mutabilidad, stack UPDATE_COMPLETE | Informe no archivado en el repositorio; ver [evidencia de la release](../evidencia/release-staging-6542326a67d664847b3ff99bd8ec3c82ca3a7c6b/README.md) |
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
