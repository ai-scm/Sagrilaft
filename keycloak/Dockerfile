# Pineada por digest para build inmutable (ver backend/Dockerfile para el
# procedimiento de actualización). Actualizada de 25.0 a 26.7 (última estable
# de la serie 26.x) aprovechando que la plataforma aún no tiene usuarios ni
# tráfico real — el primer arranque contra la base de datos de staging
# ejecuta la migración automática de esquema de Keycloak.
FROM quay.io/keycloak/keycloak:26.7@sha256:37dbaf6f0722c9ec246335f36e1ef8b2e6cb960f7c27e0d8c615121a3d475a85

ARG KEYCLOAK_PORTAL_URL=https://portal.tudominio.com
ARG KEYCLOAK_FORMULARIO_URL=https://sagrilaft.tudominio.com

COPY realm-sagrilaft.json /tmp/realm-sagrilaft.template.json

USER root
RUN mkdir -p /opt/keycloak/data/import \
    && sed \
      -e "s|https://portal-interno.tudominio.com|${KEYCLOAK_PORTAL_URL}|g" \
      -e "s|https://sagrilaft.tudominio.com|${KEYCLOAK_FORMULARIO_URL}|g" \
      /tmp/realm-sagrilaft.template.json > /opt/keycloak/data/import/realm-sagrilaft.json \
    && chown keycloak:keycloak /opt/keycloak/data/import/realm-sagrilaft.json \
    && rm /tmp/realm-sagrilaft.template.json
USER keycloak
