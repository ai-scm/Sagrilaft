from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context
from alembic.script import ScriptDirectory

from infrastructure.config.configuracion import load_config
from infrastructure.persistencia.database import Base
import infrastructure.persistencia.models  # noqa: F401 — registra todos los modelos en Base.metadata
from infrastructure.persistencia.migration_guard import (
    migration_lock, report_revision, require_single_head, verify_revision,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ConfigParser interpola '%'; preservar URLs con componentes percent-encoded.
config.set_main_option("sqlalchemy.url", load_config().db_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    if os.getenv("MIGRATION_VERIFY_HEAD") == "1":
        raise RuntimeError("La verificación de esquema requiere conexión real; no admite --sql")
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        with connectable.connect() as connection:
            with migration_lock(connection):
                context.configure(connection=connection, target_metadata=target_metadata)
                verify = os.getenv("MIGRATION_VERIFY_HEAD") == "1"
                expected = require_single_head(ScriptDirectory.from_config(config).get_heads()) if verify else None
                with context.begin_transaction():
                    if verify:
                        report_revision("migration_before", context.get_context().get_current_heads(), expected)
                    context.run_migrations()
                    if verify:
                        verify_revision(connection, expected)
                if verify:
                    # Verificar también después del commit; aún se mantiene el lock.
                    actual = verify_revision(connection, expected)
                    report_revision("migration_schema_verified", actual, expected)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
