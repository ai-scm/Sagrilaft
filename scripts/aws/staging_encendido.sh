#!/usr/bin/env bash
# Enciende o apaga staging de SAGRILAFT para no pagar cómputo cuando nadie lo usa.
#
#   scripts/aws/staging_encendido.sh estado     # solo lectura
#   scripts/aws/staging_encendido.sh apagar     # programas a 0 y base de datos detenida
#   scripts/aws/staging_encendido.sh encender   # base de datos y programas arriba (~10 min)
#
# Solo actúa sobre el clúster sagrilaft-staging y su RDS. Nunca toca producción.
# Apagado sigue cobrando: NAT, balanceador, WAF, IPs, disco de la base y secretos.
# AWS vuelve a encender sola una base detenida a los 7 días: apagar de nuevo si pasa.
# Un `cdk deploy` de staging deja los programas en 1: encender antes de desplegar,
# porque CloudFormation no puede modificar una base detenida.
set -euo pipefail

CLUSTER=sagrilaft-staging
COPIAS_ENCENDIDO=1
BACKEND_MAX=2
export AWS_REGION=us-east-1
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -z "${AWS_PROFILE:-}" ] && [ -f "$RAIZ/.env" ]; then
  AWS_PROFILE="$(grep -E '^AWS_PROFILE=' "$RAIZ/.env" | cut -d= -f2 || true)"
  export AWS_PROFILE
fi

servicios() {
  aws ecs list-services --cluster "$CLUSTER" --query 'serviceArns[]' --output text | tr '\t' '\n' | grep -v '^$'
}

nombre_corto() {
  sed -E 's#.*EcsFargate##; s#Service[0-9A-F]{8}-.*##' <<<"$1"
}

backend_resource_id() {
  servicios | grep 'BackendService' | sed -E 's#^arn:aws:ecs:[^:]+:[0-9]+:service/#service/#'
}

db_id() {
  local id
  # La base vigente es la que pertenece a la pila. Una base anterior conservada
  # (RETAIN) tras cambiar el disco queda fuera de la pila y no se toca.
  id="$(aws cloudformation describe-stack-resources --stack-name SagrilaftStack-staging \
    --query "StackResources[?ResourceType=='AWS::RDS::DBInstance'].PhysicalResourceId" \
    --output text)"
  if [ -z "$id" ] || [ "$(wc -w <<<"$id")" -ne 1 ]; then
    echo "No se encontró una única base de datos de staging: '$id'" >&2
    exit 1
  fi
  echo "$id"
}

db_estado() {
  aws rds describe-db-instances --db-instance-identifier "$1" --query 'DBInstances[0].DBInstanceStatus' --output text
}

estado() {
  echo "Programas (deseadas / en ejecución):"
  for s in $(servicios); do
    read -r deseadas activas < <(aws ecs describe-services --cluster "$CLUSTER" --services "$s" \
      --query 'services[0].[desiredCount,runningCount]' --output text)
    printf '  %-14s %s / %s\n' "$(nombre_corto "$s")" "$deseadas" "$activas"
  done
  echo "Base de datos: $(db_estado "$(db_id)")"
}

esperar_servicios() {
  local lista
  lista="$(servicios | tr '\n' ' ')"
  # shellcheck disable=SC2086
  aws ecs wait services-stable --cluster "$CLUSTER" --services $lista
}

apagar() {
  local db backend
  db="$(db_id)"
  backend="$(backend_resource_id)"
  echo "Bajando el autoescalado del backend a 0 (si no, AWS lo vuelve a encender)..."
  aws application-autoscaling register-scalable-target --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount --resource-id "$backend" \
    --min-capacity 0 --max-capacity 0 >/dev/null
  for s in $(servicios); do
    aws ecs update-service --cluster "$CLUSTER" --service "$s" --desired-count 0 --query 'service.serviceName' --output text >/dev/null
    echo "  $(nombre_corto "$s") -> 0"
  done
  echo "Esperando a que se detengan los programas..."
  esperar_servicios
  case "$(db_estado "$db")" in
    available)
      echo "Deteniendo la base de datos (tarda unos minutos)..."
      aws rds stop-db-instance --db-instance-identifier "$db" --query 'DBInstance.DBInstanceStatus' --output text ;;
    stopped|stopping) echo "La base de datos ya está detenida." ;;
    *) echo "La base de datos está en '$(db_estado "$db")'; no se detiene. Repetir más tarde." ;;
  esac
  echo "Staging apagado. Recuerda: AWS reinicia la base sola a los 7 días."
}

encender() {
  local db backend
  db="$(db_id)"
  backend="$(backend_resource_id)"
  case "$(db_estado "$db")" in
    stopped)
      echo "Encendiendo la base de datos..."
      aws rds start-db-instance --db-instance-identifier "$db" --query 'DBInstance.DBInstanceStatus' --output text ;;
    available) echo "La base de datos ya está encendida." ;;
    *) echo "La base de datos está en '$(db_estado "$db")'; se espera a que quede disponible." ;;
  esac
  echo "Esperando a la base de datos (5-10 minutos)..."
  aws rds wait db-instance-available --db-instance-identifier "$db"
  for s in $(servicios); do
    aws ecs update-service --cluster "$CLUSTER" --service "$s" --desired-count "$COPIAS_ENCENDIDO" --query 'service.serviceName' --output text >/dev/null
    echo "  $(nombre_corto "$s") -> $COPIAS_ENCENDIDO"
  done
  echo "Restaurando el autoescalado del backend ($COPIAS_ENCENDIDO a $BACKEND_MAX)..."
  aws application-autoscaling register-scalable-target --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount --resource-id "$backend" \
    --min-capacity "$COPIAS_ENCENDIDO" --max-capacity "$BACKEND_MAX" >/dev/null
  echo "Esperando a que los programas estén sanos..."
  esperar_servicios
  estado
  echo "Staging encendido."
}

case "${1:-}" in
  estado) estado ;;
  apagar) apagar ;;
  encender) encender ;;
  *) echo "Uso: $0 estado|apagar|encender" >&2; exit 2 ;;
esac
