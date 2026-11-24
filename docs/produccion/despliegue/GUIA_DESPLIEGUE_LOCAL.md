# Guía de despliegue (staging y producción)

Cómo publicar una versión nueva y cómo cambiar la infraestructura de un ambiente que ya
existe, desde un computador. Si algo falla, ver el
[runbook](../../operacion/RUNBOOK_OPERATIVO.md#ecs).

Hay dos tipos de despliegue y no se mezclan:

- **Release (código nuevo):** se publican las imágenes y `deploy_release.py` migra la
  base y actualiza los servicios. Pasos 1 a 4.
- **Cambio de infraestructura** (alarmas, parámetros, red, capacidad): `cdk deploy` con
  el contexto completo del ambiente. Ver [Cambios de infraestructura](#infraestructura).

`deploy_release.py` rechaza cualquier cambio que no sea de imagen. Por eso un cambio de
infraestructura va antes y por separado.

**Las cuatro imágenes van juntas.** Backend, formulario, portal y Keycloak usan el mismo
tag: el SHA completo del commit. Si se publica solo una y se despliega, ECS no encuentra
las otras tres, el despliegue falla con `CannotPullContainerError` y se revierte.

Todo se ejecuta desde la raíz del repositorio, con una sesión de AWS activa.

<a id="ci"></a>
## Qué hace el CI y qué no

El [CI](../../../.github/workflows/ci.yml) corre en cada PR y en cada push a `main`, y
**solo revisa**: no entra a AWS, no publica imágenes y no despliega. No usa roles, variables
ni secretos de GitHub. Tiene cuatro revisiones:

| Revisión | Qué comprueba |
|---|---|
| Secretos (gitleaks) | Que no se haya subido una contraseña o llave en ningún commit |
| Backend | `pytest`, las plantillas `.env` (`validate_envs.py`) y, solo como aviso, librerías con fallas conocidas (`pip-audit`) |
| Frontend | Pruebas del formulario (`vitest`), que el formulario y el portal compilen y, como aviso, `npm audit` |
| Infraestructura | Tipos (`tsc`), pruebas de `infra/sagrilaft/test/` y que la plantilla de staging y la de producción se generen (`cdk synth` con valores ficticios y sin consultar AWS) |

Lo que el CI no hace se hace con esta guía: publicar imágenes (paso 1), desplegar (pasos 2
a 4) y revisar el `cdk diff` de un cambio de infraestructura contra AWS
([abajo](#infraestructura)). Quien cambie la infraestructura pega el resumen del diff en
el PR.

Está preparado, sin activar, un rol solo para publicar en staging desde GitHub
([`infra/sagrilaft/policies/github-staging/`](../../../infra/sagrilaft/policies/github-staging/README.md)).
Lo que falta configurar en GitHub está en [P11 y P12](../PENDIENTES_PRODUCCION.md#p11).

<a id="build"></a>
## Paso 1: publicar las imágenes en ECR

Requisitos: Python 3.12 o posterior, Docker, un checkout limpio y el SHA completo
(40 caracteres) igual a `HEAD`. El script construye desde `git archive`, así que solo
entran los archivos del commit. Las imágenes se construyen para `linux/amd64`.

```bash
export SHA_ACTUAL='<SHA_COMPLETO>'
export CUENTA_AWS='<CUENTA_AWS>'
python3 scripts/despliegue/build_and_push_ecr_images.py \
  --environment staging --account "$CUENTA_AWS" \
  --env-file .env.staging --tag "$SHA_ACTUAL" \
  --manifest /tmp/ecr-staging-intento-1.json
```

- Para producción: `--environment prod --env-file .env.prod`.
- En vez de `--env-file` se puede usar `--from-ssm`, que lee la configuración de build de
  SSM, o `--from-environment`, que la lee de variables del proceso.
- `--manifest` debe ser un archivo nuevo. Guarda, por imagen, el repositorio, el digest y
  la huella de la configuración. Solo `complete: true` significa que las cuatro quedaron
  publicadas y verificadas; su campo `digests` es el que va al plan de la release.
- Los repositorios son inmutables: un tag publicado no se puede sobrescribir. El script
  nunca usa `latest`.

**Si falla a mitad.** Conservar el manifiesto parcial y repetir con
`--reuse-manifest <manifiesto-anterior> --manifest <manifiesto-nuevo>`. El script
reutiliza solo las imágenes que ese manifiesto acredita y construye las que faltan. Si un
`push` terminó pero no se pudo leer su digest, hay que detenerse y revisar antes de
reintentar.

Otras cosas que conviene saber:

- Las imágenes base usan tags, no digests: reconstruir el mismo SHA puede dar otro
  digest. Para volver atrás se reutilizan las imágenes ya publicadas, nunca se
  reconstruyen.
- ECR conserva las últimas 30 imágenes por repositorio. Antes de contar con una versión
  anterior para volver atrás, comprobar que siga ahí.
- Inmutable no impide borrar una imagen y volver a crear el mismo tag.
- Dos publicaciones del mismo SHA en el mismo computador no pueden correr a la vez: el
  script toma un `flock` en `/tmp/sagrilaft-publication-<hash>.lock` y falla de inmediato
  si otra lo tiene. No borrar ese archivo. El bloqueo no protege entre computadores.

<a id="coordinado"></a>
## Paso 2: preparar y revisar la release

[deploy_release.py](../../../scripts/despliegue/deploy_release.py) ordena todo: toma un
lock en S3, migra la base con la imagen nueva mientras siguen activos los servicios
viejos, comprueba la revisión de Alembic, activa los servicios, verifica tareas y
digests, y corre la prueba de humo. No construye imágenes ni crea el stack.

1. Preparar un plan privado a partir del
   [ejemplo](../../../scripts/despliegue/deploy_release.example.json): cuenta, ambiente,
   contexto completo de CDK, capacidad, tag anterior y candidato, revisiones de Alembic
   previa y objetivo, los cuatro digests y la prueba de humo.
   - `mode: compatible` exige que el código anterior siga funcionando con la base ya
     migrada.
   - En producción la prueba de humo es automática:
     [smoke_readonly.py](../../../scripts/despliegue/smoke_readonly.py) (solo `GET`;
     comprueba redirección a HTTPS, HSTS, `/health` con el SHA candidato y el OIDC de
     Keycloak). Detalle en el [README de los scripts](../../../scripts/despliegue/README.md).
     No reemplaza las pruebas funcionales.
2. Ejecutar la revisión previa (consulta AWS y sintetiza, pero no cambia nada):

```bash
python3 scripts/despliegue/deploy_release.py --environment staging \
  --plan /ruta/privada/plan-staging.json \
  --evidence-dir /ruta/privada/evidencia-staging-nueva
```

3. Revisar las plantillas y la evidencia que deja en el directorio. El script rechaza
   cualquier cambio de infraestructura que no sea la imagen; si aparece uno, se separa en
   un `cdk deploy` aparte, no se salta el control.

Cada ejecución guarda `orchestrator.json` con el commit, los hashes de los scripts usados
y una copia de ellos. No modificar los scripts mientras corre una release, y no usar el
mismo directorio de evidencia para dos ejecuciones a la vez.

**Textos con tildes.** AWS devuelve `?` en lugar de las tildes al leer la plantilla
desplegada, lo que parece un cambio. El script acepta solo cinco textos antiguos con
tildes (`APPROVED_UNICODE_PAIRS`). Todo texto nuevo que llegue a AWS (alarmas, filtros,
títulos) se escribe sin tildes ni «ñ»; una prueba de infraestructura lo exige.

## Paso 3: ejecutar

Con autorización, el mismo comando con `--execute`. Si algo falla o el resultado es
dudoso, el script se detiene y deja el lock puesto: no borrarlo ni reintentar a ciegas
([runbook](../../operacion/RUNBOOK_OPERATIVO.md#despliegue-coordinado)).

<a id="smoke-manual"></a>
### Validación manual (solo staging)

Staging admite una prueba de humo hecha por una persona. En el plan:
`"smoke_mode": "manual"`, `"smoke_command": []` y
`"manual_checks": ["release_sha", "crear_y_leer_correo", "guardar_y_recuperar", "borrador_con_correo"]`.

Después de activar los servicios, el script termina con código **3**: no es un error,
significa que falta la validación. El lock queda puesto y se crean `manual-state.json` y
`manual-validation.json`. No relanzar el despliegue.

El operador entra con su usuario, usa un correo de prueba sin acceso activo y datos
ficticios:

| Comprobación | Qué guardar |
|---|---|
| `release_sha` | El JSON de `/health` con el SHA candidato, la URL y la hora |
| `crear_y_leer_correo` | Crear un acceso con un correo válido: respuesta 201 y captura del correo recibido (redactada) |
| `guardar_y_recuperar` | Guardar un teléfono ficticio y recuperarlo con código y PIN en una ventana privada: respuestas 200 y captura del valor guardado |
| `borrador_con_correo` | Confirmar que el borrador y el correo se conservan. El registro de prueba no se borra |

En `manual-validation.json` se completan `operator`, `completedAt` (fecha ISO con zona),
`formularioId` y `accesoId`, y por cada comprobación `status: "passed"` y
`evidence: ["capturas/archivo.png"]`. Si todas pasan, `status: "approved"`; si algo
falla, `failed`; si falta algo, `pending`. No guardar PIN, tokens, enlaces de acceso,
credenciales ni archivos HAR. No editar `manual-state.json` ni `lock.json`.

Revisar la evidencia (sin tocar AWS):

```bash
python3 scripts/despliegue/deploy_release.py --environment staging \
  --plan /ruta/privada/plan-staging.json \
  --evidence-dir /ruta/privada/evidencia-de-la-ejecucion \
  --close-manual
```

Con autorización, el mismo comando con `--execute` comprueba de nuevo el stack, los
servicios y el lock, guarda `manual-accepted.json` y libera el lock. Termina con
`release_completed` y código 0. El script verifica que los archivos existan, pero no
mira las capturas: esa revisión es del operador.

<a id="validacion"></a>
## Paso 4: comprobar

Esperar `UPDATE_COMPLETE`, tareas de ECS estables y destinos del balanceador sanos.
Luego:

```bash
curl -fsS "https://<dominio-del-portal>/health"
```

El campo `commit` debe ser el SHA candidato
([dominios](../configuracion/MATRIZ_AWS_CONFIG.md#datos-de-la-cuenta)). `/health` no dice
en qué revisión está la base: para eso está la evidencia de Alembic de la release.

<a id="release"></a>
## Después de una release de producción: tag y notas

`GET /health` ya dice qué commit corre, pero el tag y las notas dicen qué cambió. Hoy no
hay ningún tag ni `CHANGELOG.md` ([P01](../PENDIENTES_PRODUCCION.md#p01)).

```bash
# 1. Crear o actualizar CHANGELOG.md con lo que trae la versión
#    y, si corresponde, _VERSION_SERVICIO en backend/main.py (hoy "2.0.0").
# 2. Crear el tag sobre el commit desplegado:
git tag -a vX.Y.Z -m "Descripción corta" "$SHA_ACTUAL"
git push origin vX.Y.Z
```

<a id="infraestructura"></a>
## Cambios de infraestructura (`cdk deploy`)

Un `cdk deploy` no ejecuta migraciones. Si solo cambian alarmas, parámetros o atributos
del balanceador, no reinicia los servicios. Así se desplegaron las alarmas y la IP real
del cliente el 2026-11-23 (registro en `tmp/despliegue-prod-20261123/`, fuera de git).

1. **Partir del último plan de release ejecutado en ese ambiente**, que trae el contexto
   completo (dominios, certificado, zona, modelo de IA, proveedor de listas, NAT,
   capacidad). El tag de imagen debe ser el que corre hoy (`/health`), para no cambiar
   la versión sin querer.
2. **Leer los destinatarios vigentes de SSM** (`ALERTAS_EMAIL_DESTINATARIO`) y pasarlos
   como `snsAlertasSub`, sin imprimirlos. Si se pasa otra lista, cambian las
   suscripciones.
3. **Variables:** `AWS_PROFILE`, `AWS_REGION=us-east-1` y `CUENTA_AWS` (CDK la exige).
4. **En zsh, pasar el contexto como arreglo** (`"${CTX[@]}"`). Si se pasa como texto,
   CDK ignora los `-c` y el diff sale falso (por ejemplo, propone borrar el NAT o crear
   un certificado).
5. **Revisar `cdk diff SagrilaftStack-<ambiente>`.** Solo debe aparecer lo que se quiere
   cambiar. Cualquier cambio en servicios de ECS, IAM o la base exige revisarlo antes.
   El CI no hace este diff: pegar su resumen en el PR del cambio.
6. **En producción, tomar una copia manual de la base** ([cómo](../configuracion/ETIQUETADO_AWS.md#snapshots-de-rds)).
7. **Desplegar** con `cdk deploy SagrilaftStack-<ambiente> --require-approval never` y
   los mismos argumentos del diff. Comparar las tareas de ECS antes y después.
8. **Después**, si hace falta, la release.

En producción, `zohoSecretYaExiste=true` va siempre en el contexto: el secreto de Zoho se
creó a mano y CDK lo importa. Los scripts `npm run deploy:*` de `infra/sagrilaft` toman
el tag y los destinatarios de variables (`IMAGE_TAG`, `ALERTAS_CORTE` o `ALERTAS_STAGING`)
y no incluyen la capacidad del backend (`backendMaxCapacity`) del último plan; por eso
se parte del plan.
