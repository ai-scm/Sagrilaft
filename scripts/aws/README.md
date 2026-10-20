# AWS

Utilidades para revisar y sincronizar la configuración que vive en AWS: secretos de Secrets Manager y parámetros de runtime.

## Qué contiene

- `sync_aws_runtime_assets.py`: escribe en Secrets Manager **solo las credenciales externas a CDK** (`zoho_credentials`, `smtp_credentials` y, solo con `PROVEEDOR_LISTAS_CAUTELA=sagrilaft` y una API key real, `sagrilaft_listas_cautela_credentials`). Nunca escribe `app_secret`, `db_credentials` ni `keycloak_admin`, que genera CDK. No imprime valores.
- `audit_aws_secrets_safe.py`: hace un inventario de los secretos. Muestra metadatos, claves JSON, si un campo está vacío, su longitud y una huella SHA-256 corta por campo. Nunca muestra el valor.

## Uso de `sync_aws_runtime_assets.py`

Por defecto solo muestra el plan (dry-run). No escribe nada en AWS.

```bash
# 1. Plan (solo lectura en AWS)
python3 scripts/aws/sync_aws_runtime_assets.py --env-file .env.prod --environment prod

# 2. Escritura, solo tras revisar el plan y confirmar la cuenta objetivo
python3 scripts/aws/sync_aws_runtime_assets.py --env-file .env.prod --environment prod \
  --apply --expected-account <ID_CUENTA_OBJETIVO>
```

Protecciones:

- **Cuenta:** con `--apply` la cuenta activa (`sts get-caller-identity`) debe coincidir con `--expected-account`; si no, no se escribe nada.
- **Entorno:** el `APP_ENV` del archivo debe coincidir con `--environment` (`prod` → `production`, `staging` → `staging`).
- **Existencia:** cada secreto externo debe existir ya. El script nunca crea secretos (`create-secret`); si falta, se detiene y pide ejecutar `cdk deploy` primero.
- **Marcadores:** un valor `REPLACE_*` o vacío en una variable obligatoria aborta la sincronización.
- **Escritura parcial:** `put-secret-value` reemplaza el secreto entero. Por eso el payload incluye todos los campos del secreto externo.
- **ECR:** solo informa si los repositorios existen. CDK los crea.

Requisitos de sesión: `AWS_PROFILE` debe apuntar a la cuenta objetivo. El perfil `default`
no tiene credenciales y el script no acepta `--profile`. En producción:
`export AWS_PROFILE=PS-PowerUserAccess-874641912777`.

Orden en el primer corte (procedimiento completo en el [checklist de corte](../../docs/produccion/despliegue/CHECKLIST_CORTE_PRODUCCION.md#secretos-externos)):

1. La infraestructura de producción ya existe (`SagrilaftStack-prod`, bootstrap del 2026-10-07). No repetir el bootstrap; comprobar diferencias con `cdk diff` y los mismos argumentos.
2. `zoho_credentials` y `smtp_credentials` ya existen. El script no crea secretos.
3. **Bloqueo:** no ejecutar `--apply` mientras las credenciales de Zoho y SMTP en `.env.prod` no coincidan con las fuentes aprobadas. El dry-run no compara valores (ver la sección de limitaciones del checklist). Las claves de BD y Keycloak admin ya no están en `.env.prod` y el script no las lee. El 2026-10-20 se encontró que la identidad SMTP real de `.env.prod` es `ses-smtp-prod-sagrilaft` (distinta a la comparada el 2026-10-16); el bloqueo sigue vigente hasta repetir la comparación con esa identidad — ver la adenda en el checklist.
4. Cuando el bloqueo esté resuelto: dry-run, revisión del plan y después `--apply --expected-account <cuenta>`.
5. Comprobación posterior con `audit_aws_secrets_safe.py` contra la línea base de la sección "Línea base esperada" del checklist: los secretos de CDK no deben cambiar.

Ver también [Matriz AWS](../../docs/produccion/configuracion/MATRIZ_AWS_CONFIG.md).

## Por qué están aquí

Los dos tocan la misma capa de configuración en AWS. Uno la escribe y el otro la revisa sin exponer nada, así que conviene tenerlos juntos.
