# La imagen base es el punto de partida — como elegir el sistema operativo
# de una máquina nueva. python:3.12-slim incluye Python preinstalado en una
# versión recortada de Linux, sin herramientas que no necesitamos.
# Si el equipo migra a Python 3.13, cambiar "3.12.17-slim" aquí y probar
# que las dependencias de requirements.txt sigan funcionando.
FROM python:3.12-slim AS base

# Dos ajustes de comportamiento de Python:
# - PYTHONUNBUFFERED: los mensajes del servidor aparecen en CloudWatch
#   de inmediato, no quedan retenidos en un buffer interno. Sin esto,
#   los logs de errores pueden llegar con minutos de retraso.
# - PYTHONDONTWRITEBYTECODE: Python no genera archivos .pyc (versiones
#   compiladas del código). En un contenedor no sirven de nada y solo
#   añaden ruido.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# WeasyPrint (la librería que genera los PDFs del formulario) no funciona
# solo con Python — necesita varias librerías del sistema operativo para
# renderizar texto, fuentes y gráficos. Estas son esas librerías.
# Si en algún momento el PDF falla con errores de fuentes o de renderizado,
# la causa suele estar aquí. "fonts-liberation" es la fuente genérica de
# respaldo; se puede añadir otra con apt-get install fonts-xxx.
# El "rm -rf /var/lib/apt/lists/*" al final borra la caché de paquetes
# para que la imagen final pese menos.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libfontconfig1 \
    fonts-liberation \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Define /app como la carpeta de trabajo dentro del contenedor.
# Todos los COPY y RUN que siguen operan desde aquí.
WORKDIR /app

# Copiamos requirements.txt antes que el resto del código.
# Docker construye la imagen en capas y reutiliza las que no cambiaron.
# Como las dependencias cambian mucho menos que el código, separarlas así
# hace que la mayoría de los builds salten directamente a copiar el código,
# ahorrando varios minutos en cada despliegue.
COPY requirements.txt .

# Instala todas las dependencias de Python listadas en requirements.txt.
# "--no-cache-dir" evita guardar los paquetes descargados en disco —
# en un contenedor eso solo aumenta el tamaño de la imagen sin beneficio.
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código fuente del backend al contenedor.
# Esto incluye los routers, servicios, modelos de dominio y migraciones.
# Lo hacemos después de instalar dependencias para aprovechar el caché
# de capas explicado arriba.
COPY . .

# Por seguridad, el servidor no debe correr como administrador (root).
# Aquí creamos un usuario sin privilegios llamado "appuser" y le damos
# propiedad sobre /app. Si el proceso fuera comprometido por un atacante,
# el daño quedaría contenido: no podría modificar archivos del sistema.
# La carpeta "uploads" se crea aquí porque el proceso necesita escribir
# en ella y debe pertenecer a este usuario.
RUN groupadd -g 1001 appuser \
    && useradd -r -u 1001 -g appuser appuser \
    && mkdir -p uploads \
    && chown -R appuser:appuser /app

# A partir de aquí, todos los comandos corren como "appuser", no como root.
USER appuser

# Documenta que el proceso escucha en el puerto 8000.
# Esto es informativo — no abre el puerto por sí solo.
# El puerto se expone realmente en docker-compose.yml con la sección "ports".
EXPOSE 8000

# Comando que se ejecuta cuando el contenedor arranca.
# entrypoint.sh espera a que la base de datos esté disponible, aplica
# las migraciones pendientes (alembic upgrade head) y luego lanza Uvicorn.
# En desarrollo, docker-compose.dev.yml reemplaza este CMD por uno con
# --reload para que el servidor se reinicie al guardar código.
CMD ["sh", "entrypoint.sh"]
