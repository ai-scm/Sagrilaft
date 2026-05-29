#!/bin/sh
# Este script se ejecuta cada vez que el contenedor del backend arranca.
# Hace tres cosas en orden: espera a que la base de datos esté lista,
# aplica los cambios pendientes en su estructura, y arranca el servidor.

# Si cualquier paso falla, el script se detiene de inmediato.
# Sin esto, un error en las migraciones podría pasar desapercibido y el
# servidor arrancaría con la base de datos en un estado incorrecto.
set -e


# ── 1. Esperar a que la base de datos esté disponible ─────────────────────
#
# Cuando el servidor arranca en AWS, la base de datos (RDS) puede tardar
# entre 10 y 60 segundos en estar lista para recibir conexiones, aunque
# Docker Compose ya la marque como "healthy". Sin esta espera, el servidor
# intentaría conectarse demasiado pronto y fallaría.
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
            # Si se agotan los intentos el contenedor falla con error,
            # Docker lo registra en los logs y puede reiniciarlo si
            # restart: unless-stopped está configurado en docker-compose.yml.
            sys.exit(1)

        time.sleep(2)
EOF


# ── 2. Aplicar migraciones de base de datos ───────────────────────────────
#
# Alembic gestiona la estructura de la base de datos (tablas, columnas,
# índices). Cada vez que el código añade o modifica algo en el modelo de
# datos, se genera un archivo de migración en alembic/versions/.
#
# "upgrade head" aplica todos los archivos de migración pendientes en orden,
# dejando la base de datos sincronizada con el código que está a punto de
# arrancar. Si ya estaba al día, el comando termina en menos de un segundo
# sin hacer nada.
#
# Si una migración falla (ej: conflicto de datos), el script se detiene aquí
# gracias al "set -e" del inicio — el servidor no arranca en estado inválido.
echo "[entrypoint] Aplicando migraciones Alembic..."
alembic upgrade head


# ── 3. Arrancar el servidor ───────────────────────────────────────────────
echo "[entrypoint] Iniciando Uvicorn (workers=${UVICORN_WORKERS:-4})..."

# "exec" reemplaza este script por el proceso de Uvicorn en lugar de
# lanzarlo como proceso hijo. Esto es importante porque Docker envía
# señales de apagado (SIGTERM) al proceso principal — si Uvicorn fuera
# un hijo del script, esas señales no llegarían y el contenedor se cerraría
# de forma brusca, cortando peticiones en curso.
exec uvicorn main:app \

    # 0.0.0.0 significa "acepta conexiones de cualquier interfaz de red".
    # Es necesario porque el tráfico llega desde Nginx (otro contenedor),
    # no desde localhost. Cambiar a 127.0.0.1 rompería la comunicación
    # entre contenedores.
    --host 0.0.0.0 \

    # Puerto donde escucha la API. Nginx redirige /api a este puerto.
    # Si se cambia aquí, hay que actualizarlo también en nginx.conf.
    --port 8000 \

    # Número de procesos del servidor corriendo en paralelo.
    # Más workers = más solicitudes simultáneas. La regla habitual es
    # 2 × número de CPUs de la instancia. El valor lo define UVICORN_WORKERS
    # en .env; si no está definido, usa 4 como valor por defecto.
    --workers "${UVICORN_WORKERS:-4}" \

    # Activa la lectura de cabeceras HTTP añadidas por proxies (Nginx, ALB).
    # Sin esto, el servidor vería siempre la IP interna de Docker en lugar
    # de la IP real del usuario, y los logs de seguridad serían inútiles.
    --proxy-headers \

    # Lista de IPs o rangos desde los que se acepta confiar en esas cabeceras.
    # 172.0.0.0/8 es la red interna de Docker (donde vive Nginx).
    # Aceptar cabeceras de IPs no confiables permitiría que alguien falsifique
    # su dirección IP — por eso no se pone 0.0.0.0 aquí.
    --forwarded-allow-ips "${TRUSTED_PROXY_IPS:-127.0.0.1}"
