# Despliegue

Scripts para publicar una versión en AWS: construir y subir las imágenes Docker, preparar el plan del release, lanzar la migración de base de datos en ECS y coordinar la activación del stack.

## Qué contiene

- `build_and_push_ecr_images.py`: construye las imágenes del backend, el formulario público, el portal interno y Keycloak, y las sube a ECR etiquetadas con el SHA del commit. Lo usa el workflow de CI y también se puede ejecutar a mano.
- `deploy_release.py` y `deploy_release.sh`: orquestador del release. Prepara el plan, migra, verifica la evidencia, activa los servicios y corre el smoke test. Sin `--execute` solo consulta AWS y no modifica nada. El `.sh` es un envoltorio que llama al `.py`; lo usan los scripts `release:staging` y `release:prod` de `infra/sagrilaft`.
- `deploy_release.example.json`: plantilla del plan que recibe el orquestador. No tiene secretos. Se copia fuera del repositorio y se completa ahí.
- `smoke_readonly.py`: smoke automático de solo lectura para usarlo como `smoke_command` del plan (obligatorio en producción). Solo emite `GET`: comprueba redirección HTTP→HTTPS, respuesta HTTPS y HSTS en los tres dominios, `/health` del formulario y del portal (commit candidato y base de datos) y el documento OIDC de Keycloak. No crea accesos ni envía correos. Ejemplo: `["python3", "scripts/despliegue/smoke_readonly.py", "--environment", "prod", "--sha", "<SHA_40>", "--forms-domain", "<dominio>", "--portal-domain", "<dominio>", "--keycloak-domain", "<dominio>"]`.
- `run_ecs_migration.py` y `run_ecs_migration.sh`: lanzan la tarea de migración en ECS y revisan su resultado, sin activar servicios.

## Por qué están juntos

Son una misma cadena. `deploy_release.py` importa `run_ecs_migration.py` directamente, y el `.sh` depende de su `.py` hermano, así que deben quedarse en la misma carpeta. Además, `ORCHESTRATOR_SOURCES` en `deploy_release.py` lista estos archivos para registrar su hash en la evidencia; si se mueve alguno, hay que actualizar esa lista.

## Habilitación de pruebas en staging con dummy

Los comandos `synth:staging`, `diff:staging`, `deploy:staging:bootstrap` y
`deploy:staging` fijan explícitamente `proveedorListasCautela=dummy`.
Los comandos de producción conservan `deshabilitado`. `.env.staging` ya utiliza
`dummy`, pero ese archivo no actualiza por sí solo la configuración en AWS.

Al aplicar este cambio en el futuro, el único cambio esperado en la plantilla
con los demás contextos iguales es el valor del parámetro
`/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA`: de `deshabilitado` a `dummy`.
No requiere migraciones ni cambios del frontend. ECS inyecta el parámetro al
arrancar cada tarea; después de actualizarlo hay que renovar las tareas del
backend, ya que cambiar SSM no actualiza los contenedores existentes.

La activación requiere un cambio de configuración separado: `release:staging`
en modo `compatible` rechaza cambios SSM. No cambiar el plan de ejemplo
`deploy_release.example.json` a `dummy` para intentar incluir la activación en
una release de imágenes. Después de aplicar la configuración por separado, los
planes de releases posteriores deben reflejar `dummy` para conservarla.

### Preparar el Change Set sin introducir cambios Unicode

No reutilizar directamente la respuesta de `GetTemplate` como plantilla de
actualización: en este stack devuelve cinco textos con tildes sustituidas por
`?`. Reenviarlos introduce cambios reales en cuatro políticas ECR y un dashboard
(textos anteriores a noviembre de 2026; las alarmas y los textos nuevos se
escriben sin tildes para no sumar más). CloudFormation propaga esos cambios a
otros recursos dependientes, incluyendo definiciones de tareas y servicios ECS.

Usar el artefacto original de la última release ejecutada, disponible en el
bucket de assets CDK y referenciado por `stackTemplateAssetObjectUrl` en su
`manifest.json`. Verificar que coincide con la plantilla activa salvo por las
cinco diferencias Unicode conocidas, sin ignorar ninguna otra diferencia. Las
equivalencias de `comparison_template` sirven para verificar esa comparación;
no son una autorización para reconstruir una plantilla mediante sustituciones
de texto o para aceptar recursos adicionales en el Change Set.

Copiar ese artefacto original y cambiar exclusivamente `Properties.Value` del
parámetro de staging a `dummy`, conservando los demás bytes del artefacto cuando
sea posible. Si se vuelve a serializar, usar JSON con escapes Unicode
(`ensure_ascii=True`) y comprobar que conserva todos los valores originales.
Mantener todos los parámetros de CloudFormation con `UsePreviousValue`, además
del rol de ejecución y las capacidades previas.

Antes de ejecutar, el Change Set debe contener exactamente un `Modify` de tipo
`AWS::SSM::Parameter`, con nombre físico
`/sagrilaft/staging/config/PROVEEDOR_LISTAS_CAUTELA`, `Replacement=False` y cambio
únicamente de `Value`. Comprobar también la plantilla del Change Set contra el
artefacto candidato completo; no basta con un diff local. Cualquier recurso
adicional obliga a detener la ejecución.

Revisar tanto `describe-change-set` como su vista ampliada con
`--include-property-values`. La vista básica puede mostrar únicamente SSM
mientras la ampliada añade `MasterUserPassword` de RDS por su referencia dinámica
a Secrets Manager. Que el recurso RDS sea idéntico en ambas plantillas no basta
para descartar la diferencia de una referencia resuelta: no ignorar ese recurso,
no leer ni fijar contraseñas como parte de esta activación y no aprobar la
ejecución hasta aclarar la discrepancia. La preparación debe registrar ambas
respuestas y comprobar por separado que producción mantiene su plantilla,
estado de stack y valor/versión del parámetro SSM.

Efectos del simulador y comprobaciones:

- La disponibilidad devuelve `habilitado=true`. La consulta aparece al abrir de
  nuevo el detalle; el hook no vuelve a consultar disponibilidad periódicamente.
- Una consulta exitosa guarda un ID simulado en el expediente y permite mostrar
  la descarga. El PDF es mínimo y en blanco; no representa una consulta real ni
  requiere credenciales del proveedor o acceso de red a Tusdatos.
- Identificaciones `999…`, `888…` y `777…` simulan hallazgos de riesgo alto,
  medio y bajo; `000…` devuelve `ERROR_VERIFICACION`. Otras identificaciones
  devuelven `APROBADO_SAGRILAFT`. Hay una espera simulada de dos segundos.
- La consulta devuelve un resultado y actualiza el ID del reporte, sin cambiar
  el estado del expediente. Una nueva consulta exitosa sustituye el ID anterior;
  una consulta fallida conserva el ID existente. Usar expedientes de prueba.
- Limitación existente: la verificación admite expedientes cerrados, pero la
  descarga no. Esta activación no modifica esa regla compartida con producción.
- Verificar el flujo consulta → actualización del detalle → descarga, errores y
  bloqueos 409 con el proveedor deshabilitado. Comprobar que producción sigue
  deshabilitada y que tanto CDK como el backend rechazan `dummy` en producción.

Pruebas locales: `infra/sagrilaft/test/listas-cautela.test.ts`,
`tests/contracts/test_listas_cautela_fuente_unica.py`,
`tests/integration/test_sagrilaft_feature_flag.py` y
`tests/unit/test_deploy_release.py`. La prueba de infraestructura compara las
plantillas sintetizadas sin consultar AWS.
