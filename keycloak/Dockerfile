FROM quay.io/keycloak/keycloak:25.0

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
