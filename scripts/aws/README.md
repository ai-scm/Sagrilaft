# AWS

Utilidades para revisar y sincronizar la configuración que vive en AWS: secretos de Secrets Manager y parámetros de runtime.

## Qué contiene

- `sync_aws_runtime_assets.py`: lee un archivo de entorno (por defecto `.env.prod`) y sincroniza sus valores con Secrets Manager. No imprime los valores secretos.
- `audit_aws_secrets_safe.py`: hace un inventario de los secretos. Muestra metadatos, claves JSON, si un campo está vacío, su longitud y una huella SHA-256 corta por campo. Nunca muestra el valor.

## Por qué están aquí

Los dos tocan la misma capa de configuración en AWS. Uno la escribe y el otro la revisa sin exponer nada, así que conviene tenerlos juntos.
