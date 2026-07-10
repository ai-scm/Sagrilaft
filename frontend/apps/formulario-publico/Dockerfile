# ── Etapa 1: compilar la aplicación React ─────────────────────────────────
FROM node:22-bookworm-slim AS builder

WORKDIR /app

# Copiar código fuente y dependencias (necesario para NPM Workspaces)
COPY . .

# Instalar dependencias
RUN npm ci --ignore-scripts

ARG VITE_BACKEND_URL
ARG VITE_PORTAL_INTERNO_URL
ARG VITE_RAZON_SOCIAL
ARG VITE_CORREO_DATOS

ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_PORTAL_INTERNO_URL=${VITE_PORTAL_INTERNO_URL}
ENV VITE_RAZON_SOCIAL=${VITE_RAZON_SOCIAL}
ENV VITE_CORREO_DATOS=${VITE_CORREO_DATOS}


# Generar build optimizado para producción

RUN npm run build:publico


# ── Etapa 2: servir los archivos con Nginx ────────────────────────────────
FROM nginx:alpine

# Copiar archivos compilados
COPY --from=builder --chown=nginx:nginx /app/apps/formulario-publico/dist /usr/share/nginx/html

# Copiar configuración de Nginx
COPY --chown=nginx:nginx apps/formulario-publico/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
