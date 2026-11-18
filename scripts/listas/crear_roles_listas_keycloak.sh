#!/bin/sh
# Crea los roles de listas en un realm de Keycloak que ya existe y, opcionalmente, los asigna.
#
# `--import-realm` solo importa un realm nuevo: en staging/producción los roles agregados a
# keycloak/realm-sagrilaft.json no aparecen solos. Este script es idempotente (no falla si el
# rol o la asignación ya existen) y se ejecuta DENTRO del contenedor de Keycloak, que ya tiene
# KEYCLOAK_ADMIN y KEYCLOAK_ADMIN_PASSWORD:
#
#   Staging (ECS Exec):
#     aws ecs execute-command --cluster sagrilaft-staging --task <tarea-keycloak> \
#       --container keycloak --interactive --command "/bin/sh"
#     # y dentro, pegar este script o ejecutarlo con:  sh crear_roles_listas_keycloak.sh [usuario:rol ...]
#
#   Local:
#     docker exec -i solucion-keycloak-1 sh -s -- usuario1:listas_revisor < scripts/listas/crear_roles_listas_keycloak.sh
#
# Argumentos opcionales: asignaciones usuario:rol (rol = listas_operador | listas_revisor).
# Los usuarios también necesitan acceso_clientes y/o acceso_proveedores para ver expedientes.
set -eu

KCADM=/opt/keycloak/bin/kcadm.sh
REALM="${KEYCLOAK_REALM:-sagrilaft}"
SERVIDOR="${KEYCLOAK_LOCAL_URL:-http://localhost:8080}"

: "${KEYCLOAK_ADMIN:?Falta KEYCLOAK_ADMIN en el contenedor}"
: "${KEYCLOAK_ADMIN_PASSWORD:?Falta KEYCLOAK_ADMIN_PASSWORD en el contenedor}"

"$KCADM" config credentials --server "$SERVIDOR" --realm master \
  --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null

crear_rol() {
  if "$KCADM" get "roles/$1" -r "$REALM" >/dev/null 2>&1; then
    echo "Rol $1: ya existe"
  else
    "$KCADM" create roles -r "$REALM" -s "name=$1" -s "description=$2" >/dev/null
    echo "Rol $1: creado"
  fi
}

crear_rol listas_operador "Listas cautelares: consultar y ver el historial y el informe interno"
crear_rol listas_revisor "Listas cautelares: además revisar coincidencias, abrir el PDF del proveedor y forzar consultas (gasta créditos)"

for asignacion in "$@"; do
  usuario="${asignacion%%:*}"
  rol="${asignacion#*:}"
  case "$rol" in
    listas_operador|listas_revisor) ;;
    *) echo "Rol no permitido en $asignacion (use listas_operador o listas_revisor)" >&2; exit 2 ;;
  esac
  "$KCADM" add-roles -r "$REALM" --uusername "$usuario" --rolename "$rol"
  echo "Usuario $usuario: rol $rol asignado"
done
