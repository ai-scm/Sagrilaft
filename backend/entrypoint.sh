#!/bin/sh
# Este script se ejecuta cada vez que el contenedor del backend arranca.
# Espera a que la base de datos esté lista y luego arranca el servidor.
# En ECS, las migraciones se ejecutan como task puntual antes del deploy.

# Si cualquier paso falla, el script se detiene de inmediato.
set -e

if [ "${APP_ENV:-development}" = "production" ] || [ "${APP_ENV:-development}" = "staging" ]; then
    if [ "${STORAGE_BACKEND:-local}" != "s3" ]; then
        echo "[entrypoint] ERROR: APP_ENV=${APP_ENV} requiere STORAGE_BACKEND=s3." >&2
        exit 1
    fi

    if [ -z "${S3_BUCKET:-}" ]; then
        echo "[entrypoint] ERROR: APP_ENV=${APP_ENV} requiere S3_BUCKET." >&2
        exit 1
    fi
fi


# ── 1. Esperar a que la base de datos esté disponible ─────────────────────
#
# Cuando el servidor arranca en ECS, la base de datos (RDS) puede tardar
# entre 10 y 60 segundos en estar lista para recibir conexiones. En desarrollo
# local tambien evita que el backend arranque antes que PostgreSQL.
#
# El bloque python - <<'EOF' ... EOF ejecuta un script Python escrito
# directamente aquí dentro del shell, sin necesidad de un archivo separado.
python - <<'EOF'
import os, sys, time
import sqlalchemy as sa

url      = os.environ["DATABASE_URL"]
intentos = 30  # 30 intentos × 2 segundos = hasta 60 segundos de espera.
               # Aumentar si RDS tarda más en escenarios de cold start.

for i in range(1, intentos + 1):
    try:
        with sa.create_engine(url).connect() as conn:
            # "SELECT 1" es la consulta más ligera posible — solo confirma
            # que la base de datos responde. No lee ni escribe datos reales.
            conn.execute(sa.text("SELECT 1"))

        print(f"[entrypoint] Base de datos disponible (intento {i}).", flush=True)
        sys.exit(0)

    except Exception as e:
        # Se registra solo el tipo de error (ej: OperationalError), no el
        # mensaje completo, para evitar que credenciales de la BD aparezcan
        # en los logs de CloudWatch.
        print(f"[entrypoint] BD no disponible ({i}/{intentos}): {type(e).__name__}", flush=True)

        if i == intentos:
            # Si se agotan los intentos el contenedor falla con error.
            # En ECS, el servicio intentara reemplazar la task fallida.
            sys.exit(1)

        time.sleep(2)
EOF


# ── 2. Aplicar migraciones de base de datos solo cuando se solicite ───────
#
# Alembic gestiona la estructura de la base de datos (tablas, columnas,
# índices). Cada vez que el código añade o modifica algo en el modelo de
# datos, se genera un archivo de migración en alembic/versions/.
#
if [ "${RUN_MODE:-server}" = "migrate" ]; then
    echo "[entrypoint] Aplicando migraciones Alembic..."
    alembic upgrade head
    echo "[entrypoint] Migraciones completadas."
    exit 0
fi


# ── 3. Arrancar el servidor ───────────────────────────────────────────────
echo "[entrypoint] Iniciando Uvicorn (workers=${UVICORN_WORKERS:-4})..."

# "exec" reemplaza este script por el proceso de Uvicorn en lugar de
# lanzarlo como proceso hijo. Esto es importante porque Docker envía
# señales de apagado (SIGTERM) al proceso principal — si Uvicorn fuera
# un hijo del script, esas señales no llegarían y el contenedor se cerraría
# de forma brusca, cortando peticiones en curso.
# Parámetros del servidor:
#   --host 0.0.0.0: Acepta conexiones de cualquier interfaz de red (necesario para Nginx/frontend en Docker).
#   --port 8000: Puerto donde escucha la API.
#   --workers: Número de procesos paralelos.
#   --proxy-headers: Activa la lectura de cabeceras HTTP de proxies.
#   --forwarded-allow-ips: Rango de IPs permitidas para confiar en cabeceras de proxy.
#   --timeout-keep-alive: Segundos que Uvicorn mantiene una conexión keep-alive abierta.
#     Debe ser mayor al idleTimeout del ALB (300 s) para evitar la race condition en la
#     que Uvicorn cierra el socket TCP justo antes de que el ALB lea la respuesta.
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-4}" \
    --proxy-headers \
    --forwarded-allow-ips "${TRUSTED_PROXY_IPS:-127.0.0.1}" \
    --timeout-keep-alive 310
