"""Exclusión cooperativa de migraciones y comprobación de revisión Alembic."""

from contextlib import contextmanager
import json
import os
import time

from alembic.runtime.migration import MigrationContext
from sqlalchemy import text


# Clave estable compartida por todas las releases; el lock es por base de datos.
# Session-level para sobrevivir commits/autocommit de las migraciones.
MIGRATION_LOCK_KEY = 0x53414752494C


@contextmanager
def migration_lock(connection):
    """Requiere conexión exclusiva sin transacción previa; no bloquea la app.

    La espera limita la contención con otros migradores, no la duración del DDL.
    Todas las herramientas que migren esta BD deben respetar la misma clave.
    """
    if connection.dialect.name != "postgresql":
        yield
        return
    if connection.in_transaction():
        raise RuntimeError("La conexión de migración debe iniciar sin transacción")
    try:
        timeout = int(os.getenv("MIGRATION_LOCK_TIMEOUT_SECONDS", "60"))
    except ValueError:
        raise RuntimeError("MIGRATION_LOCK_TIMEOUT_SECONDS debe ser entero") from None
    if not 0 <= timeout <= 3600:
        raise RuntimeError("MIGRATION_LOCK_TIMEOUT_SECONDS debe estar entre 0 y 3600")
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
            ).scalar_one()
            # El SELECT abre una transacción SQLAlchemy; cerrarla antes de que
            # Alembic decida quién es dueño de la transacción del DDL.
            connection.commit()
            if acquired:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Otra migración mantiene el bloqueo de PostgreSQL")
            time.sleep(min(0.2, remaining))
        yield
    finally:
        if acquired:
            # Descartar transacciones fallidas antes de intentar el unlock.
            if connection.in_transaction():
                connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )
            connection.commit()


def require_single_head(heads):
    if len(heads) != 1:
        raise RuntimeError("La imagen debe contener exactamente un head Alembic")
    return heads[0]


def verify_revision(connection, expected):
    actual = MigrationContext.configure(connection).get_current_heads()
    if actual != (expected,):
        raise RuntimeError(f"Revisión Alembic inesperada: {actual!r}; esperada: {expected}")
    return actual


def report_revision(event, revisions, expected):
    # Solo revisiones; no URL, credenciales, filas ni configuración completa.
    print(json.dumps({"event": event, "revisions": list(revisions), "expectedHead": expected}), flush=True)
