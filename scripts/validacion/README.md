# Validación

Comprobaciones que se ejecutan antes de desplegar. No modifican AWS.

## Qué contiene

- `validate_envs.py`: revisa que las plantillas `.env.dev.example`, `.env.staging.example` y `.env.prod.example` tengan todas las variables declaradas para cada entorno. Corre en CI.
- `check_staging_readiness.py`: revisa que el repositorio esté listo para intentar staging: configuración de CDK, Dockerfiles, build args y contratos de webhooks. No valida DNS, ACM, ECS ni secretos reales; esos quedan pendientes.
- `test_migrations_pg16.py`: aplica las migraciones sobre un clúster temporal de PostgreSQL 16 por socket Unix. No usa Docker, AWS ni la base de datos de la aplicación. Requiere tener los binarios de PostgreSQL 16 instalados.

## Por qué están aquí

Son chequeos previos que responden a una pregunta: ¿está listo esto? Ninguno cambia producción, y por eso se agrupan aparte de los scripts que sí despliegan.
