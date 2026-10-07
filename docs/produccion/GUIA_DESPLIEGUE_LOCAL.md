# Guía de Despliegue Local (Staging / Prod)

Función única: despliegue rutinario desde local sobre un ambiente existente,
build/push compartido y registro de release. El primer corte se ejecuta con el
[procedimiento específico](CHECKLIST_CORTE_PRODUCCION.md). Para incidentes usar
el [runbook](../operacion/RUNBOOK_OPERATIVO.md#ecs). Estado y tareas no se registran aquí.

## El Concepto Clave: Consistencia de Etiquetas (Tags)
La arquitectura actual en CDK exige que **los 4 contenedores de la plataforma (Frontend, Backend, Portal y Keycloak)** utilicen exactamente la misma etiqueta de imagen (el SHA aprobado para la release).

Si intentas compilar y subir solo un contenedor (ej. solo el Backend) y haces un despliegue, AWS ECS buscará esa misma etiqueta para los otros tres. Al no encontrarlos, AWS activará el *Circuit Breaker*, cancelará el despliegue (`CannotPullContainerError`) y hará un Rollback.

Las cuatro imágenes deben existir con ese SHA antes de activar la release. El publicador
construye las que faltan y solo reutiliza las existentes mediante un manifiesto revisado.
No publica ni sobrescribe `latest`.

---

## Publicación y despliegue coordinado

Abre tu terminal asegurándote de estar en la **raíz del proyecto** (no dentro de la carpeta infra) y con tus credenciales de AWS CLI activas.

<a id="build"></a>
### Paso 1: Compilar y subir todas las imágenes (ECR)
El publicador requiere Python 3.12 o posterior, un checkout limpio y el SHA completo
(de 40 caracteres) coincidente con `HEAD`. Construye desde `git archive`: solo incluye
archivos registrados del commit, no archivos ignorados ni artefactos locales. La
configuración de build se entrega mediante argumentos explícitos obtenidos del archivo
de ambiente; CI usa `--from-environment`. Se construye para `linux/amd64`.

Antes de publicar verifica cuenta y los cuatro repositorios: deben ser exactamente
`IMMUTABLE`, sin exclusiones. La declaración CDK prepara esa política, pero **debe
aplicarse en una operación de infraestructura separada y aprobada** antes de usar el
publicador. Este script no cambia la política ECR. Los tags `latest` antiguos pueden
permanecer; no se actualizan ni se utilizan para estas releases.

```bash
export SHA_ACTUAL='<SHA_COMPLETO_APROBADO>'
export CUENTA_AWS='<CUENTA_DEL_CATALOGO>'
python3 scripts/build_and_push_ecr_images.py \
  --environment staging --account "$CUENTA_AWS" \
  --env-file .env.staging --tag "$SHA_ACTUAL" \
  --manifest /tmp/ecr-staging-intento-1.json
```

Para producción usar `--environment prod --env-file .env.prod`. El manifiesto de salida
debe ser un archivo nuevo. Registra cuenta, región, ambiente, SHA, plataforma y, por
imagen, repositorio, digest, huella de configuración y resultado. Solo `complete: true`
acredita las cuatro imágenes verificadas; el campo `digests` puede copiarse al plan de
`deploy_release` tras revisarlo. No autoriza el despliegue ni acredita migraciones o smoke.

Si falla una publicación, conservar el manifiesto parcial. Para reutilizar imágenes ya
acreditadas, revisar esa evidencia y pasarla explícitamente en otro intento:

```bash
python3 scripts/build_and_push_ecr_images.py \
  --environment staging --account "$CUENTA_AWS" \
  --env-file .env.staging --tag "$SHA_ACTUAL" \
  --reuse-manifest /tmp/ecr-staging-intento-1.json \
  --manifest /tmp/ecr-staging-intento-2.json
```

El publicador compara repositorio, digest y huella de configuración; no reconstruye ni
adopta automáticamente un tag existente. Si el push terminó pero no pudo acreditarse
su digest, detenerse y reconciliar la evidencia antes de reintentar. Un cambio de
configuración de build para una imagen ya publicada requiere una nueva release/commit.
Los Dockerfiles aún usan tags de imágenes base: reconstruir el mismo SHA no garantiza
el mismo digest. El rollback reutiliza el SHA/digests anteriores ya publicados y exige
compatibilidad del esquema; no reconstruye imágenes. La retención ECR sigue en 30
imágenes por repositorio: hay que verificar que el artefacto de retorno siga disponible.

**Concurrencia local:** antes de usar Docker, el publicador adquiere un `flock`
exclusivo por registro/SHA en `/tmp/sagrilaft-publication-<hash>.lock`, compartido
entre checkouts. Lo mantiene durante build, push, verificación del digest y guardado
de cada imagen. Si otra ejecución lo tiene, falla inmediatamente sin iniciar Docker;
no espera ni reintenta automáticamente. Build/push heredan el descriptor para mantener
el bloqueo si termina el proceso padre mientras esos comandos siguen ejecutándose.
Al cerrarse los descriptores se libera el lock; el archivo permanece y **no debe
borrarse** para evitar que dos procesos bloqueen inodos diferentes. Un error de acceso
al archivo detiene la publicación. Se requiere un sistema POSIX con `flock`.

La protección abarca ejecuciones de este publicador en una misma máquina con `/tmp`
compartido. Para un daemon Docker remoto compartido entre máquinas o contenedores con
`/tmp` separados, usar un único publicador: este lock no es distribuido. Comandos
Docker manuales o scripts antiguos no participan en él.

**Límite de IMMUTABLE y conservación pendiente:** `IMMUTABLE` protege contra
sobrescribir un tag que existe; no impide borrar la imagen y recrear después el mismo
tag. Si ya fue borrada y no se aporta evidencia previa, el publicador puede considerar
el SHA ausente y reconstruirlo. Si se aporta un manifiesto que acredita esa imagen,
se detiene al detectar que falta. Por ello no se garantiza una asociación histórica
permanente SHA/digest mediante la política de inmutabilidad por sí sola.

La retención permanece en **30 imágenes por repositorio**, sin cambios. **Antes de
operar debemos definir la conservación de releases de rollback y sus manifiestos,
y los controles de borrado/recreación de tags.** Conservar solo el manifiesto no
permite recuperar una imagen eliminada ni garantiza reconstruir su mismo digest.

CI usa este mismo publicador y conserva el manifiesto incluso si es parcial. Un rerun
con tags existentes se detiene sin evidencia aprobada; su reutilización se realiza con
`--reuse-manifest` desde local. No se implementa adopción automática de artefactos de
otra ejecución de CI.

<a id="coordinado"></a>
### Paso 2: Preparar y revisar el despliegue coordinado

El flujo implementado está en [deploy_release.py](../../scripts/deploy_release.py).
Los comandos directos `deploy:staging`/`deploy:prod` de CDK son operaciones de
infraestructura: **no ejecutan migraciones ni sustituyen esta barrera**.
No activar una release que exige otro esquema antes de verificar su migración.

1. Preparar un plan privado a partir del [ejemplo](../../scripts/deploy_release.example.json):
   cuenta/ambiente, contexto completo, capacidad, tag anterior y candidato,
   revisiones previa/objetivo, cuatro digests y validación funcional aprobada.
   Por defecto se exige `smoke_command`; staging admite la modalidad manual descrita abajo.
   `compatible` exige que el código anterior pueda leer y escribir después de migrar.
   `bootstrap` exige un stack ya existente con cero tareas; el orquestador no lo crea.
2. Con las imágenes publicadas/verificadas, ejecutar solo el preflight:

```bash
python3 scripts/deploy_release.py --environment staging \
  --plan /ruta/privada/plan-staging.json \
  --evidence-dir /ruta/privada/evidencia-staging-nueva
```

Sin `--execute` consulta AWS y sintetiza localmente; no es un ensayo offline.
Cada ejecución registra `orchestrator.json`: commit base, checkout modificado,
hashes SHA-256 y copia de los scripts en `orchestrator-sources/`. El commit base
no identifica por sí solo cambios sin confirmar; el snapshot identifica el código
local utilizado, independientemente del SHA candidato de las imágenes. Cada intento
de cierre conserva su propio registro `orchestrator-close-<id>.json` y snapshot.
No modificar los scripts durante una ejecución.

Los JSON del orquestador y `events.jsonl` se escriben mediante temporal privado en
el mismo directorio, sincronización, reemplazo atómico y sincronización del directorio.
Un error posterior al reemplazo puede dejar el archivo nuevo completo aunque se
reporte fallo de sincronización. No es una transacción con AWS. Logs de subprocess y
assemblies CDK se generan progresivamente y pueden quedar parciales si se interrumpen.
Se requiere un único escritor por directorio de evidencia.

Revisar las plantillas preparadas y la evidencia antes de autorizar otra fase.
Rechaza cambios ajenos a las transiciones admitidas: separarlos, no omitir el control.
Excepción aprobada solo para staging: `STAGING_UNICODE_PAIRS` en el orquestador
admite ocho pares completos de texto en rutas exactas (cuatro descripciones de
LifecyclePolicyText ECR, tres AlarmDescription y el fragmento del título del
dashboard). GetTemplate devuelve `?` donde los recursos directos conservan tildes.
La equivalencia solo se aplica a copias para comparación: no cambia las assemblies,
no omite propiedades ni normaliza Unicode de forma general. Cualquier otro texto,
ruta, retención o imagen sigue sujeto a comparación estricta. No se aplica a prod.


3. Solo con autorización de ejecución, el mismo flujo con `--execute` adquiere el
   lock S3, prepara la imagen de migración manteniendo el código anterior, ejecuta
   el lanzador verificado, comprueba evidencia Alembic y después activa servicios,
   verifica tareas/digests y ejecuta el smoke automático o queda pendiente de validación
   manual en staging (código 3, lock conservado). No construye imágenes.
4. Un fallo o resultado incierto detiene el avance y conserva el lock; no se debe
   borrar ni reintentar a ciegas. Ver [recuperación](../operacion/RUNBOOK_OPERATIVO.md#despliegue-coordinado).

El cambio aislado de ECR no demuestra que el diff del próximo plan sea aceptable.
Alcance validado y seguimiento: [P20](PENDIENTES_PRODUCCION.md#p20).

<a id="smoke-manual"></a>
### Validación manual de staging

Modalidad implementada localmente; todavía no acredita un ensayo real. El plan usa
`"smoke_mode": "manual"`, `"smoke_command": []` y `"manual_checks":
["release_sha", "crear_y_leer_correo", "guardar_y_recuperar", "borrador_con_correo"]`.
Solo staging la admite. Los planes sin `smoke_mode` conservan el smoke automático.
El preflight no realiza esta validación ni exige evidencia posterior a la activación.

Después de activar/verificar ECS, el código de salida **3** significa pendiente,
no éxito ni fallo de migración. Se conserva el lock sin TTL y se generan
`manual-state.json` y `manual-validation.json`. No relanzar el despliegue para cerrarlo.

El operador usa su login habitual, un correo controlado sin acceso activo y datos
ficticios. No se necesitan archivos de sesión. Recorrido mínimo:

| Clave | Comprobación y evidencia |
|---|---|
| `release_sha` | JSON de `/health` con commit candidato, URL y fecha/hora; vincular con tareas/digests verificados. |
| `crear_y_leer_correo` | Crear acceso único con correo válido; HTTP 201, IDs y captura de lectura posterior del correo, redactado. Puede enviar un correo real. |
| `guardar_y_recuperar` | Guardar teléfono ficticio y recuperar por código/PIN en ventana privada; HTTP 200 de guardado/recuperación y captura del valor persistido para el mismo formulario. |
| `borrador_con_correo` | Confirmar borrador y correo conservados. Registrar que se retiene el registro de prueba, sin borrado automático. |

No repetir casos inválidos cubiertos localmente ni ejecutar adjuntos, radicación,
IA o firma. La evidencia Alembic acredita el esquema; la configuración del backend
vincula el recorrido HTTP con RDS. Una captura sola no identifica la base de datos.

Guardar los archivos redactados dentro del directorio de esta ejecución. En
`manual-validation.json`, completar `operator`, `completedAt` (ISO 8601 con zona),
`formularioId`, `accesoId`; por cada comprobación poner `status: "passed"` y
`evidence: ["capturas/archivo.png"]`. Solo si todas pasan, `status: "approved"`.
Ante fallo usar `failed`; si falta algo dejar `pending`. Mantener los identificadores
runId/planHash/SHA generados y `retention: "retained_no_delete_endpoint"`.
No guardar PIN, tokens, enlaces completos de acceso, credenciales ni HAR.
El responsable registrado revisará cualquier limpieza futura como operación separada.

Revisión local de evidencia (sin consultas ni escrituras AWS):

```bash
python3 scripts/deploy_release.py --environment staging \
  --plan /ruta/privada/plan-staging.json \
  --evidence-dir /ruta/privada/evidencia-de-la-ejecucion \
  --close-manual
```

Solo tras revisar las capturas y autorizar el cierre, añadir `--execute` a ese comando.
**Ese cierre consulta AWS y elimina condicionalmente el lock propio**, sin desplegar
ni migrar. Verifica cuenta, stack, plantilla activa, servicios/digests y ETag del lock;
archiva `manual-accepted.json` con hashes de evidencia antes de liberar. El éxito es
`release_completed` y código 0. No usar esta operación para resolver fallos de migración.

El validador exige archivos existentes y no vacíos, pero no interpreta capturas ni
certifica la veracidad de la declaración humana. La revisión del operador es necesaria.
Evidencia inválida, estado cambiado o resultado incierto no se consideran éxito;
seguir el [runbook](../operacion/RUNBOOK_OPERATIVO.md#despliegue-coordinado).
Conservar localmente plan/evidencia; no editar `manual-state.json` ni `lock.json`.
El cierre usa bloqueo local POSIX; no ejecutar cierres concurrentes desde copias de evidencia.

<a id="validacion"></a>
### 3. Monitoreo
Esperar `UPDATE_COMPLETE`, verificar tareas ECS y target groups saludables, y
comprobar el endpoint del ambiente. CloudFormation completo no sustituye los smoke tests.

Definir `PORTAL_VALIDACION` con la URL del portal del ambiente en el
[catálogo](checklist-valores-staging-prod.md) y ejecutar:

```bash
curl -fsS "${PORTAL_VALIDACION}/health"
```

El campo `commit` debe coincidir con el SHA candidato. `/health` no acredita por sí
solo la revisión Alembic ni compatibilidad de esquema: exigir la evidencia de migración
y un smoke de lectura/escritura que recorra el cambio.

<a id="release"></a>
### 4. Después de un deploy a PRODUCCIÓN: tag + CHANGELOG (2026-07-30)
El backend expone el commit exacto corriendo en `GET /health` (campo `commit`),
así que **no es obligatorio** taguear para saber qué versión está desplegada
en un incidente. Aun así, para que el equipo pueda leer *qué cambió* entre
versiones (no solo *qué commit* corre), después de un deploy exitoso a
producción:

```bash
# 1. Crear CHANGELOG.md si todavía no existe; mover "Sin publicar" a una sección
#    nueva con el número de versión, y actualizar _VERSION_SERVICIO en
#    backend/main.py si corresponde.

# 2. Crear el tag de git sobre el commit desplegado
git tag -a v2.1.0 -m "Descripción corta del release" $SHA_ACTUAL
git push origin v2.1.0
```

---

## Diagnóstico

Usar el [runbook ECS](../operacion/RUNBOOK_OPERATIVO.md#ecs) para eventos
CloudFormation/ECS y logs. La lista de herramientas y comandos de incidentes
se mantiene allí, sin una segunda copia en esta guía.
