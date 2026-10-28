# ── Etapa 1: compilar la aplicación React ─────────────────────────────────
# Pineada por digest para build inmutable (ver backend/Dockerfile).
FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS builder

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
# Pineada por digest para build inmutable (ver backend/Dockerfile).
FROM nginx:alpine@sha256:a3554c0d0b48177b1413c26e01f695334428020d9df01243fbae3e11cfd17417

RUN sed -i 's/listen\s*80;/listen 8080;/' /etc/nginx/conf.d/default.conf \
    && sed -i '/^user/d' /etc/nginx/nginx.conf \
    && sed -i 's|/var/run/nginx.pid|/tmp/nginx.pid|' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

# Copiar archivos compilados
COPY --from=builder --chown=nginx:nginx /app/apps/formulario-publico/dist /usr/share/nginx/html

# Copiar configuración de Nginx
COPY --chown=nginx:nginx apps/formulario-publico/nginx.conf /etc/nginx/conf.d/default.conf

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
