# ── Etapa 1: compilar la aplicación React ─────────────────────────────────
#
# Esta etapa solo existe para construir los archivos finales (HTML, JS, CSS).
# Una vez que termina, Docker la descarta — el servidor web nunca ve Node.js.
# Esto mantiene la imagen final pequeña y sin herramientas de desarrollo expuestas.
# Use the Debian slim variant to avoid known high-severity vulnerabilities
# present in some alpine-based Node images. The slim image is still small but
# generally receives more timely security updates for system packages.
# Use the newer Debian bookworm slim variant to pick up more recent
# security updates and reduce reported vulnerabilities in base image.
FROM node:22.24.0-bookworm-slim AS builder

# Carpeta de trabajo dentro del contenedor durante la compilación.
WORKDIR /app

# Copiamos solo los archivos de dependencias antes que el código fuente.
# Docker guarda en caché cada paso; si package.json no cambió, reutiliza la
# instalación anterior y el build siguiente tarda segundos en vez de minutos.
COPY package*.json ./

# Instala las dependencias tal como están congeladas en package-lock.json.
# --ignore-scripts bloquea scripts automáticos que algunos paquetes ejecutan
# al instalarse — un vector habitual de ataques a cadena de suministro.
# Si alguna dependencia falla aquí, revisar si realmente necesita scripts de
# instalación; la mayoría no los necesita.
RUN npm ci --ignore-scripts

# Copiamos el resto del código después de instalar dependencias para aprovechar
# la caché de Docker explicada arriba.
COPY . .

# Genera los archivos estáticos finales en /app/dist.
# Este comando lee las variables VITE_* del entorno en tiempo de build,
# no en tiempo de ejecución — si cambias una variable de entorno del frontend
# debes reconstruir la imagen con docker compose build frontend.
RUN npm run build


# ── Etapa 2: servir los archivos con Nginx ────────────────────────────────
#
# nginx-unprivileged es la variante oficial mantenida por el equipo de seguridad
# de Nginx Inc. La diferencia clave respecto a la imagen estándar es que ningún
# proceso corre como root: ni el master ni los workers. Esto elimina el riesgo
# de escalada de privilegios si el servidor web fuera comprometido, y reduce
# el número de CVEs reportadas porque no necesita los binarios de root.
# Usa el puerto 8080 internamente porque los usuarios no-root en Linux no pueden
# abrir puertos por debajo de 1024. Desde fuera sigue siendo el puerto 80
# — el mapeo lo hace docker-compose.yml.
# Use the Debian slim variant of the unprivileged Nginx image to reduce
# reported vulnerabilities versus alpine-based images.
FROM nginxinc/nginx-unprivileged:1.27-bookworm-slim

# Copiamos los archivos compilados desde la etapa builder.
# --chown asigna propiedad al usuario nginx directamente al copiar.
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

# Copiamos la configuración de Nginx: rutas, proxy hacia /api, compresión, etc.
# Si necesitas ajustar cabeceras de caché, añadir HTTPS, o cambiar el proxy,
# edita nginx.conf — no este Dockerfile.
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

# El proceso escucha en el puerto 8080 (no 80) porque corre sin root.
# docker-compose.yml mapea el puerto 80 del host a este 8080 interno.
EXPOSE 8080

# Arranca Nginx en primer plano. "daemon off" es obligatorio en Docker:
# si Nginx se pusiera en segundo plano, el contenedor creería que el proceso
# terminó y se detendría solo.
CMD ["nginx", "-g", "daemon off;"]
