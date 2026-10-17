#!/usr/bin/env bash
set -euo pipefail

# Contrato y comprobaciones en el helper; no ejecuta CDK ni activa servicios.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/run_ecs_migration.py" "$@"
