# Procedimiento del primer corte a producción

Función única: ordenar la ejecución y la evidencia requerida. Este archivo no
registra progreso mediante casillas: cada resultado se registra en el ID de
[PENDIENTES_PRODUCCION.md](PENDIENTES_PRODUCCION.md#corte) correspondiente.
Los ejemplos se ejecutan en Bash desde la raíz del proyecto, salvo los bloques
que entran explícitamente a `infra/sagrilaft` mediante un subshell.

Secuencia revisada contra los scripts el 2026-10-06; no ejecutada en producción.
Consultar el [estado acreditado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).
Para despliegues posteriores usar la [guía rutinaria](GUIA_DESPLIEGUE_LOCAL.md).

## Fase 0 — Preparación

Consultar [P01](PENDIENTES_PRODUCCION.md#p01), [P02](PENDIENTES_PRODUCCION.md#p02)
y [P08](PENDIENTES_PRODUCCION.md#p08): seleccionar SHA validado, disponer de
aprobación previa de negocio/Compliance y rollback, y confirmar en la síntesis que
el ALB prepara `Strict-Transport-Security: max-age=31536000`. La verificación del
encabezado y de HTTP→HTTPS se hará después del bootstrap y antes de abrir el servicio
a usuarios (P08).
Los criterios que requieren un stack se comprueban antes de abrir el servicio
a usuarios reales; no confundir aprobación previa con Go/No-Go final.

Verificar identidad AWS, cuenta y región contra el
[catálogo](checklist-valores-staging-prod.md), disponibilidad de Docker y del
archivo privado `.env.prod`. Fijar `SHA_ACTUAL` al commit aprobado (no asumir
que HEAD es la release). Preparar SMTP para cargarlo después del bootstrap.
La clase RDS seleccionada para producción es `db.t3.medium`; la instancia sigue
siendo de una sola AZ, con 7 días de backup y sin ensayo de recuperación
productiva. Este riesgo se aceptó para el primer corte; P10 sigue abierto para
el ensayo de restauración y medición del RTO. La aceptación no sustituye el Go
formal ni el procedimiento de rollback; consultar P02 y P10.
La lista SNS vigente del catálogo fue confirmada para producción. Después del
bootstrap, cada destinatario debe confirmar su suscripción; P06 no cierra hasta
verificar las once confirmaciones y una alarma de extremo a extremo.

<a id="contexto"></a>
## Contexto común de CDK

Definir en la misma sesión Bash, usando los valores del
[catálogo](checklist-valores-staging-prod.md), incluida su
[lista de destinatarios](checklist-valores-staging-prod.md#destinatarios):

```bash
export SHA_ACTUAL='<SHA_APROBADO>'
export IMAGE_TAG="$SHA_ACTUAL"
export BEDROCK_MODEL_ID='<MODELO_DEL_CATALOGO>'
export ALERTAS_CORTE='<LISTA_DE_DESTINATARIOS_DEL_CATALOGO>'
CONTEXTO_PROD=(
  -c zohoSecretYaExiste=true
  -c proveedorListasCautela=deshabilitado
  -c "snsAlertasSub=$ALERTAS_CORTE"
)
```

Reemplazar los marcadores antes de ejecutar. Reutilizar este contexto en
**todas** las invocaciones, incluidas las posteriores al bootstrap: CDK no
persiste flags entre comandos. Los scripts prod ya habilitan NAT. La identidad
SES se importa desde el dominio existente; Zoho se importa por el flag común.
La API key de listas no es exigible con el proveedor deshabilitado.

## Fase 1 — Bootstrap sin tareas activas

Seguimiento: [P04](PENDIENTES_PRODUCCION.md#p04).

```bash
(cd infra/sagrilaft && npm run deploy:prod:bootstrap -- "${CONTEXTO_PROD[@]}")
```

Esperar CloudFormation completo y guardar outputs. Verificar `desiredCount=0`.
Este paso crea ECR antes del primer push. El tag `bootstrap-placeholder` del
script solo sirve para registrar task definitions sin arrancarlas; no ejecutar
la migración con esa imagen.

## Fase 2 — Configuración e imágenes

Seguimiento de configuración: [P03](PENDIENTES_PRODUCCION.md#p03).
Cargar SMTP con consola/archivo privado en Secrets Manager según la
[matriz](MATRIZ_AWS_CONFIG.md); verificar las claves de Zoho sin imprimir valores.
DB, app_secret y admin Keycloak los genera CDK. Verificar S3/SSM y los outputs.

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
[P20](PENDIENTES_PRODUCCION.md#p20); ejecución productiva: [P04](PENDIENTES_PRODUCCION.md#p04).

## Fase 6 — Validación antes de abrir a usuarios

Ejecutar los criterios del registro único y adjuntar evidencia productiva:

| Registro | Procedimiento |
|---|---|
| [P05 — firma automática](PENDIENTES_PRODUCCION.md#p05) | [Runbook Zoho](../operacion/RUNBOOK_OPERATIVO.md#zoho) |
| [P06 — alarma real](PENDIENTES_PRODUCCION.md#p06) | [Runbook alarmas](../operacion/RUNBOOK_OPERATIVO.md#alarmas) |
| [P07 — smoke funcional/correo](PENDIENTES_PRODUCCION.md#p07) | Recorrido del [E2E de referencia](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md), archivado como ejecución productiva independiente |

## Fase 7 — Registro y decisión final

Adjuntar los resultados al Go/No-Go de P02, incluidos criterios 2 y 7. Ante un
criterio fallido aplicar el rollback acordado. Registrar resultados y cierre
en cada ID; actualizar [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md)
con fecha y SHA. Publicar tag/notas mediante la
[guía de release](GUIA_DESPLIEGUE_LOCAL.md#release).
