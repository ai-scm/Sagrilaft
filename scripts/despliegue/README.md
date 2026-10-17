# Despliegue

Scripts para publicar una versión en AWS: construir y subir las imágenes Docker, preparar el plan del release, lanzar la migración de base de datos en ECS y coordinar la activación del stack.

## Qué contiene

- `build_and_push_ecr_images.py`: construye las imágenes del backend, el formulario público, el portal interno y Keycloak, y las sube a ECR etiquetadas con el SHA del commit. Lo usa el workflow de CI y también se puede ejecutar a mano.
- `deploy_release.py` y `deploy_release.sh`: orquestador del release. Prepara el plan, migra, verifica la evidencia, activa los servicios y corre el smoke test. Sin `--execute` solo consulta AWS y no modifica nada. El `.sh` es un envoltorio que llama al `.py`; lo usan los scripts `release:staging` y `release:prod` de `infra/sagrilaft`.
- `deploy_release.example.json`: plantilla del plan que recibe el orquestador. No tiene secretos. Se copia fuera del repositorio y se completa ahí.
- `run_ecs_migration.py` y `run_ecs_migration.sh`: lanzan la tarea de migración en ECS y revisan su resultado, sin activar servicios.

## Por qué están juntos

Son una misma cadena. `deploy_release.py` importa `run_ecs_migration.py` directamente, y el `.sh` depende de su `.py` hermano, así que deben quedarse en la misma carpeta. Además, `ORCHESTRATOR_SOURCES` en `deploy_release.py` lista estos archivos para registrar su hash en la evidencia; si se mueve alguno, hay que actualizar esa lista.
