# Procedimiento del primer corte a producción

Función única: ordenar la ejecución y la evidencia requerida. Este archivo no
registra progreso mediante casillas: cada resultado se registra en el ID de
[PENDIENTES_PRODUCCION.md](../PENDIENTES_PRODUCCION.md#corte) correspondiente.
Los ejemplos se ejecutan en Bash desde la raíz del proyecto, salvo los bloques
que entran explícitamente a `infra/sagrilaft` mediante un subshell.

Secuencia revisada contra los scripts el 2026-10-16 (credenciales actualizadas el 2026-10-20). Estado de AWS verificado el 2026-10-16:
la infraestructura de producción **ya existe** (`SagrilaftStack-prod`, `CREATE_COMPLETE` desde el
2026-10-07, con `desiredCount=0`). No hay servicios activos ni migración ejecutada; el primer
corte productivo aún no ha comenzado. La [incoherencia de `.env.prod`](#bloqueo-env-prod)
que bloqueaba la sincronización de secretos se resolvió el 2026-10-20.
Consultar el [estado acreditado](../../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).
Para despliegues posteriores usar la [guía rutinaria](GUIA_DESPLIEGUE_LOCAL.md).

## Fase 0 — Preparación

Consultar [P01](../PENDIENTES_PRODUCCION.md#p01), [P02](../PENDIENTES_PRODUCCION.md#p02)
y [P08](../PENDIENTES_PRODUCCION.md#p08): seleccionar SHA validado, disponer de
aprobación previa de negocio/Compliance y rollback, y confirmar en la síntesis que
el ALB prepara `Strict-Transport-Security: max-age=31536000`. La verificación del
encabezado y de HTTP→HTTPS se hará después del bootstrap y antes de abrir el servicio
a usuarios (P08).
Los criterios que requieren un stack se comprueban antes de abrir el servicio
a usuarios reales; no confundir aprobación previa con Go/No-Go final.

Verificar identidad AWS, cuenta y región contra el
[catálogo](../configuracion/checklist-valores-staging-prod.md), disponibilidad de Docker y del
archivo privado `.env.prod`. Fijar `SHA_ACTUAL` al commit aprobado (no asumir
que HEAD es la release). Preparar SMTP para cargarlo después del bootstrap.
El riesgo aceptado de la RDS de producción (clase, una sola AZ, retención de
backups) y sus límites están en [P02](P02_GO_NO_GO_ROLLBACK.md#riesgo-rds-aceptado-para-el-primer-corte);
el ensayo de restauración pendiente está en [P10](../PENDIENTES_PRODUCCION.md#p10).
La lista SNS vigente del catálogo fue confirmada para producción. Después del
bootstrap, cada destinatario debe confirmar su suscripción; P06 no cierra hasta
verificar las once confirmaciones y una alarma de extremo a extremo.

<a id="contexto"></a>
## Contexto común de CDK

Definir en la misma sesión Bash, usando los valores del
[catálogo](../configuracion/checklist-valores-staging-prod.md), incluida su
[lista de destinatarios](../configuracion/checklist-valores-staging-prod.md#destinatarios):

```bash
export SHA_ACTUAL='<SHA_APROBADO>'
export IMAGE_TAG="$SHA_ACTUAL"
export BEDROCK_MODEL_ID='<MODELO_DEL_CATALOGO>'
export ALERTAS_CORTE='<LISTA_DE_DESTINATARIOS_DEL_CATALOGO>'
export CUENTA_AWS='<CUENTA_AWS>'
export HOSTED_ZONE_ID='<HOSTED_ZONE_ID>'
export CERTIFICATE_ARN='<ARN_CERTIFICADO_ACM>'
export ALERTAS_STAGING='<CORREO_ALERTAS_STAGING>'
export AWS_REGION='us-east-1'
export AWS_PROFILE='PS-PowerUserAccess-<CUENTA_AWS>'
CONTEXTO_PROD=(
  -c zohoSecretYaExiste=true
  -c proveedorListasCautela=deshabilitado
  -c "snsAlertasSub=$ALERTAS_CORTE"
)
```

`AWS_PROFILE` es obligatorio: el perfil `default` no tiene credenciales, y ni
`audit_aws_secrets_safe.py` ni `sync_aws_runtime_assets.py` aceptan `--profile`. Todos
los comandos AWS de esta sesión dependen de esa variable. `CUENTA_AWS` es el valor
confirmado en el [catálogo](../configuracion/checklist-valores-staging-prod.md#criterios-confirmados).

Reemplazar los marcadores de SHA, modelo y destinatarios antes de ejecutar. Reutilizar
este contexto en **todas** las invocaciones de CDK: CDK no persiste flags entre comandos.

**Advertencia sobre scripts de CDK.** `deploy:prod` y `diff:prod` de
`infra/sagrilaft/package.json` no fijan `desiredCount`, así que su valor por defecto
es `2` y arrancarían servicios. Para cualquier comando previo a la migración usar el
equivalente de `deploy:prod:bootstrap` (`-c desiredCount=0 -c imageTag=bootstrap-placeholder`).
Un `diff:prod` sin esos flags muestra cambios falsos (`desiredCount` 0→2 y tags
`synth-placeholder`) que no corresponden al bootstrap.

## Fase 1 — Bootstrap sin tareas activas

Seguimiento: [P04](../PENDIENTES_PRODUCCION.md#p04).

**Estado verificado el 2026-10-16:** el bootstrap ya se ejecutó el 2026-10-07 y es intencional.
`SagrilaftStack-prod` está en `CREATE_COMPLETE`; `DatabasePostgres` (`db.t3.medium`, una
AZ, retención de 7 días) está `available`; los cuatro servicios ECS tienen `desiredCount=0`
y `runningCount=0`. **No repetir el bootstrap**: la infraestructura ya existe.

Prerrequisito verificado: `sagrilaft/prod/zoho_credentials` existe en la cuenta objetivo,
creado el 2026-09-24 y no programado para borrado. Comprobación sin valores:

```bash
aws secretsmanager describe-secret --secret-id sagrilaft/prod/zoho_credentials \
  --region "$AWS_REGION" --query Name --output text
```

Si una comprobación futura no lo encuentra, detenerse: la creación manual es la excepción
documentada en el [runbook, sección Zoho](../../operacion/RUNBOOK_OPERATIVO.md#zoho) y debe
quedar registrada en P04 antes de continuar.

**Comprobación de diferencias antes de cualquier cambio de infraestructura.** Usar los mismos
argumentos que el bootstrap, sin desplegar:

```bash
(cd infra/sagrilaft && cdk diff --no-color \
  -c environment=prod -c account="$CUENTA_AWS" -c region="$AWS_REGION" \
  -c hostedZoneName=ia.blend360.com -c hostedZoneId=<HOSTED_ZONE_ID> \
  -c domainName=forms-sagrilaft.ia.blend360.com -c portalDomainName=sagrilaft.ia.blend360.com \
  -c keycloakDomainName=login-sagrilaft.ia.blend360.com \
  -c certificateArn=<ARN_CERTIFICADO_ACM> \
  -c imageTag=bootstrap-placeholder -c desiredCount=0 -c bedrockModelId=amazon.nova-pro-v1:0 \
  -c habilitarNatEgress=true "${CONTEXTO_PROD[@]}")
```

Resultado del 2026-10-16: `There were no differences` para `SagrilaftStack-prod`. Cualquier
diferencia debe revisarse y registrarse en P04 antes de desplegar. Un `cdk deploy` solo
procede tras esa revisión y con los mismos argumentos.

Reglas que siguen vigentes: el tag `bootstrap-placeholder` solo registra task definitions sin
arrancarlas; no ejecutar la migración con esa imagen, y mantener `desiredCount=0` hasta la
activación.

## Fase 2 — Configuración e imágenes

Seguimiento de configuración: [P03](../PENDIENTES_PRODUCCION.md#p03).
Las credenciales externas (Zoho, SMTP) ya están cargadas en AWS y conciliadas con `.env.prod`; su eventual reescritura
depende de la [condición de bloqueo](#bloqueo-env-prod) y del procedimiento de
[secretos externos](#secretos-externos). DB, app_secret y admin Keycloak los genera CDK y el
procedimiento nunca los escribe. Verificar S3/SSM y los outputs.

<a id="secretos-externos"></a>
### Secretos externos: procedimiento

Solo el script [`sync_aws_runtime_assets.py`](../../../scripts/aws/sync_aws_runtime_assets.py)
escribe secretos en esta fase. Escribe únicamente `zoho_credentials` y `smtp_credentials`,
más `sagrilaft_listas_cautela_credentials` si `PROVEEDOR_LISTAS_CAUTELA=sagrilaft` y la
API key tiene valor real. Con el proveedor deshabilitado, ese último secreto queda
omitido. Nunca escribe `app_secret`, `db_credentials` ni `keycloak_admin`.

<a id="bloqueo-env-prod"></a>
**Condición de bloqueo (verificada el 2026-10-16; RESUELTA el 2026-10-20, ver cierres más abajo).** Entonces `.env.prod` no coincidía con los secretos
vigentes en AWS para Zoho y SMTP. Comparación solo de igualdad, sin valores:

| Elemento | Resultado | Lectura |
|---|---|---|
| `zoho_credentials`: los cuatro campos | Todos distintos de `.env.prod` | El runbook (sección 9) indica que el secreto contiene la cuenta oficial de Legal y que `.env.prod` conserva la cuenta operativa anterior. |
| `smtp_credentials.username` | Coincide con la clave **activa** de `sagrilaft-ses-smtpp` (creada el 2026-10-07) | El `SMTP_USER` de `.env.prod` no coincide con ninguna de las 61 claves IAM revisadas. Probablemente es la clave eliminada a las 08:54 del 2026-10-07. |
| `smtp_credentials.password` | Distinta de `.env.prod` | La contraseña solo se puede validar con una prueba de envío o confirmación del responsable. |

Las claves de base de datos y Keycloak admin (`KEYCLOAK_DB_*`, `KEYCLOAK_ADMIN*`, `SECRET_KEY`)
se eliminaron de `.env.prod` el 2026-10-19: ningún script local las lee, así que ya no forman
parte de esta condición. Su fuente vigente es AWS (`db_credentials`, `keycloak_admin`, `app_secret`).

**Consecuencia (histórica; vigente solo si `.env.prod` vuelve a divergir):** ejecutar `--apply` con un `.env.prod` desactualizado **sobrescribiría** los secretos
correctos de Zoho y SMTP con valores desactualizados, y dejaría SMTP apuntando a una clave
revocada. **Condiciones para ejecutar `--apply` (1 y 2 cumplidas el 2026-10-20; falta revisar el dry-run):**

1. `.env.prod` se corrige con los valores aprobados por el responsable de Zoho y SMTP,
   o se decide explícitamente conservar los valores actuales de AWS.
2. Tras la corrección, la comparación de igualdad de la tabla debe coincidir con la fuente
   aprobada, con evidencia registrada en P03.
3. Se revisa el dry-run completo (paso 4).

Los secretos de Zoho y SMTP de AWS siguen siendo la fuente vigente; `.env.prod` ya coincide con ellos.

Requisitos: Fase 1 verificada (los secretos de CDK y `smtp_credentials` ya existen) y
`.env.prod` privado con `APP_ENV=production`. Las tareas ECS leen los secretos al
arrancar: la sincronización debe completarse **antes** de la migración de la Fase 3–5.

**Cierre SMTP (2026-10-20).** La identidad SMTP de producción es `ses-smtp-prod-sagrilaft`
(no `sagrilaft-ses-smtpp`, como indicaba la verificación del 2026-10-16). `.env.prod` y el
secreto `sagrilaft/prod/smtp_credentials` en AWS ya coinciden con esa identidad; login y
envío real fueron probados exitosamente.

**Cierre Zoho (2026-10-20).** Se confirmó en la consola de Zoho (Self Client, API Console)
que el `client_id`/`client_secret` de `sagrilaft/prod/zoho_credentials` son los correctos
de la cuenta oficial de Legal — la "cuenta operativa anterior" que tenía `.env.prod` quedó
descartada. `.env.prod` y `.env.staging` se corrigieron para coincidir con sus respectivos
secretos (`sagrilaft/prod/zoho_credentials` y `sagrilaft/staging/zoho_credentials`),
comparación por hash verificada campo a campo. Los webhooks de Zoho Sign
(`Sagrilaft-Produccion` y `Sagrilaft-Staging`), que se habían borrado, se recrearon con la
configuración documentada en el [catálogo](../configuracion/checklist-valores-staging-prod.md).

**Ambas condiciones de la tabla de bloqueo quedan cerradas.** `sync_aws_runtime_assets.py
--apply` ya no está bloqueado por esta condición — sigue aplicando el resto del
procedimiento (pasos 1-7 de la Fase 2) antes de ejecutarlo. Detalle en
[P03](../PENDIENTES_PRODUCCION.md#p03).

**Verificación real (2026-10-20).** El `refresh_token` de `sagrilaft/staging/zoho_credentials` y
`sagrilaft/prod/zoho_credentials` autentica contra Zoho: HTTP 200 y `access_token` recibido
en ambos. El webhook recreado se probó con una firma real en staging: expediente `SAG-9C58BEF6`,
cuatro entregas `POST /api/webhooks/zoho-sign` con `200 OK`, expediente pasó a `FIRMADO` sin
intervención manual. Queda cerrado.

**Línea base esperada (2026-10-16).** Antes de cualquier escritura, los secretos de CDK y los
externos deben tener estas fechas de último cambio:

| Secreto | `LastChangedDate` esperado | Origen registrado |
|---|---|---|
| `app_secret` | 2026-10-07 08:00:34 (-05:00) | CloudFormation (creación) |
| `keycloak_admin` | 2026-10-07 08:00:35 (-05:00) | CloudFormation (creación) |
| `db_credentials` | 2026-10-07 08:13:19 (-05:00) | CloudFormation (`SecretTargetAttachment` con RDS) |
| `smtp_credentials` | 2026-10-07 09:05:41 (-05:00) | `PutSecretValue` manual del operador |
| `zoho_credentials` | 2026-09-24 13:03:11 (-05:00) | Carga manual de la cuenta oficial |

Cualquier fecha distinta en CDK indica un cambio no explicado y detiene el corte.

**1. Identidad y cuenta.** Confirmar que la cuenta activa es la del catálogo, con el perfil
exportado en el contexto común:

```bash
aws sts get-caller-identity --query Account --output text   # debe ser "$CUENTA_AWS"
```

**2. Instantánea previa (fuera del repositorio).** Guarda metadatos y huellas, sin valores.
El auditor lee cada valor para calcular la huella SHA-256, pero no lo imprime:

```bash
EVIDENCIA_DIR="$HOME/evidencia-secretos-prod-$SHA_ACTUAL"
mkdir -p -m 700 "$EVIDENCIA_DIR"
python3 scripts/aws/audit_aws_secrets_safe.py --region "$AWS_REGION" --prefix sagrilaft/prod/ \
  > "$EVIDENCIA_DIR/antes.json"
```

**3. Dry-run (no escribe).**

```bash
python3 scripts/aws/sync_aws_runtime_assets.py --env-file .env.prod --environment prod \
  --region "$AWS_REGION" | tee "$EVIDENCIA_DIR/dry-run.txt"
```

**4. Revisión del plan.** Antes de continuar, comprobar en `dry-run.txt`:

- Cabecera `modo DRY-RUN (sin cambios)` y ningún `ERROR`.
- `zoho_credentials` y `smtp_credentials` aparecen como `se actualizaría` con los campos esperados
  (cuatro para Zoho, `username` y `password` para SMTP).
- `sagrilaft_listas_cautela_credentials` aparece como `omitido` mientras el proveedor sea `deshabilitado`.
- `app_secret`, `db_credentials` y `keycloak_admin` aparecen solo como `administrado por CDK, NO se escribe`.
- Los cuatro repositorios ECR aparecen como `existe`.

Si aparece un `ERROR`, detenerse: no ejecutar `--apply` con un plan incompleto.

**Limitaciones del dry-run.** El dry-run solo verifica que existan los nombres de secreto,
que los campos estén presentes y que no haya marcadores `REPLACE_*`. **No** verifica que los
valores de `.env.prod` sean correctos ni coincidan con AWS, **no** detecta claves IAM revocadas
ni credenciales caducadas, y **no** comprueba la cuenta de SES. Por eso la coherencia de valores
se verifica con la tabla de la [condición de bloqueo](#bloqueo-env-prod) antes del dry-run, y
el dry-run no sustituye esa verificación.

**5. Ejecución explícita.** Solo tras la revisión y con la cuenta verificada:

```bash
python3 scripts/aws/sync_aws_runtime_assets.py --env-file .env.prod --environment prod \
  --region "$AWS_REGION" --apply --expected-account "$CUENTA_AWS"
```

El script vuelve a comprobar la cuenta y el `APP_ENV` antes de escribir; si no coinciden,
no escribe nada. Cada secreto escrito aparece como `actualizado` y el resultado final
como `Terminado.`

**6. Instantánea posterior y comparación.** Guardar la nueva instantánea y comparar:

```bash
python3 scripts/aws/audit_aws_secrets_safe.py --region "$AWS_REGION" --prefix sagrilaft/prod/ \
  > "$EVIDENCIA_DIR/despues.json"

python3 - "$EVIDENCIA_DIR/antes.json" "$EVIDENCIA_DIR/despues.json" <<'EOF'
import json, sys
antes = {r["name"]: r for r in json.load(open(sys.argv[1]))}
despues = {r["name"]: r for r in json.load(open(sys.argv[2]))}
# Línea base verificada el 2026-10-16 (ver tabla de la sección "Línea base esperada").
BASE = {
    "app_secret": "2026-10-07 08:00:34",
    "keycloak_admin": "2026-10-07 08:00:35",
    "db_credentials": "2026-10-07 08:13:19",
}
EXTERNOS = {"zoho_credentials": "2026-09-24 13:03:11", "smtp_credentials": "2026-10-07 09:05:41"}
for name, r in despues.items():
    base = name.rsplit("/", 1)[-1]
    previo = antes.get(name, {})
    if base in BASE:
        cambio_fuera_de_linea = not r["last_changed"].startswith(BASE[base])
        cambio_desde_antes = previo.get("field_summary") != r["field_summary"]
        ok = not cambio_fuera_de_linea and not cambio_desde_antes
        print("CDK      ", "OK sin cambios" if ok else "REVISAR: cambió", name)
    elif base in EXTERNOS:
        esperado_posterior = not r["last_changed"].startswith(EXTERNOS[base])
        ok = not r["empty_fields"] and esperado_posterior
        print("EXTERNO  ", "OK" if ok else "REVISAR", name, "campos vacíos:", r["empty_fields"])
EOF
```

Criterios de aceptación: los tres secretos de CDK dicen `OK sin cambios` (fecha igual a la línea
base y sin cambios frente a la instantánea previa); los dos externos dicen `OK`, no tienen campos
vacíos y tienen una fecha posterior a la línea base. Cualquier `REVISAR` detiene el corte.

Esta comparación no verifica que los valores de los externos sean los aprobados: eso requiere la
condición de bloqueo resuelta, con evidencia registrada en P03.

**7. Registro.** Anotar en [P03](../PENDIENTES_PRODUCCION.md#p03) la fecha, el SHA, la cuenta
verificada y el resultado de ambas comparaciones. No copiar valores ni archivos de
`$EVIDENCIA_DIR` al repositorio.

Verificar también S3/SSM y los outputs de la Fase 1.

Construir y publicar las cuatro imágenes con el mismo SHA mediante el
[paso de build/push de la guía](GUIA_DESPLIEGUE_LOCAL.md#build), usando `prod`
y `.env.prod`. Confirmar las cuatro imágenes antes de continuar.

## Fases 3–5 — Preparación, migración y activación coordinadas

<a id="migracion"></a>
Conservar el orden: stack con cero tareas → imagen real de migración → migración
verificada → activación. Usar el modo `bootstrap` del flujo descrito en la
[guía única](GUIA_DESPLIEGUE_LOCAL.md#coordinado), con el contexto productivo completo.
El tag anterior debe reflejar el bootstrap existente; el candidato identifica las
cuatro imágenes publicadas. Revisar el preflight antes de autorizar ejecución.

CDK permite `migrationImageTag` independiente de `imageTag`; registrar una task
definition no ejecuta Alembic. El lanzador actual sí espera y valida resultado,
imagen y digest; el contenedor y el orquestador verifican la revisión de esquema.
No usar el antiguo comando sin imagen/digest/token esperados ni duplicar aquí
la implementación manual de espera. La guía define el contrato coordinado.

El primer corte productivo no está ejecutado. Validación del flujo y recuperación:
[P20](../PENDIENTES_PRODUCCION.md#p20); ejecución productiva: [P04](../PENDIENTES_PRODUCCION.md#p04).

## Fase 6 — Validación antes de abrir a usuarios

Ejecutar los criterios del registro único y adjuntar evidencia productiva:

| Registro | Procedimiento |
|---|---|
| [P05 — firma automática](../PENDIENTES_PRODUCCION.md#p05) | [Runbook Zoho](../../operacion/RUNBOOK_OPERATIVO.md#zoho) |
| [P06 — alarma real](../PENDIENTES_PRODUCCION.md#p06) | [Runbook alarmas](../../operacion/RUNBOOK_OPERATIVO.md#alarmas) |
| [P07 — smoke funcional/correo](../PENDIENTES_PRODUCCION.md#p07) | Recorrido del [E2E de referencia](../../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md), archivado como ejecución productiva independiente |

## Fase 7 — Registro y decisión final

Adjuntar los resultados al Go/No-Go de P02, incluidos criterios 2 y 7. Ante un
criterio fallido aplicar el rollback acordado. Registrar resultados y cierre
en cada ID; actualizar [Estado](../../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md)
con fecha y SHA. Publicar tag/notas mediante la
[guía de release](GUIA_DESPLIEGUE_LOCAL.md#release).
