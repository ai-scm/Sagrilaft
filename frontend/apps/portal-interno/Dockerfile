# ── Etapa 1: compilar la aplicación React ─────────────────────────────────
FROM node:22-bookworm-slim AS builder

WORKDIR /app

# Copiar código fuente y dependencias (necesario para NPM Workspaces)
COPY . .

# Instalar dependencias
RUN npm ci --ignore-scripts

ARG VITE_BACKEND_URL
ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM=sagrilaft
ARG VITE_KEYCLOAK_CLIENT_ID=sagrilaft-portal

ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}
ENV VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM}
ENV VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}




# Generar build optimizado para producción
RUN npm run build:portal


# ── Etapa 2: servir los archivos con Nginx ────────────────────────────────
FROM nginx:alpine

# Copiar archivos compilados
COPY --from=builder --chown=nginx:nginx /app/apps/portal-interno/dist /usr/share/nginx/html

# Copiar configuración de Nginx
COPY --chown=nginx:nginx apps/portal-interno/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
