#!/usr/bin/env python3
"""P20 B only: isolated Alembic fixture; never advances the project's revision."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

REVISION = 'p20b_expand_01'
COLUMN = 'p20_b_probe'
VERSION_TABLE = 'p20_b_alembic_version'
ENVIRONMENT = '''from alembic import context
config = context.config
options = dict(version_table='p20_b_alembic_version', version_table_schema='public')
if context.is_offline_mode():
    context.configure(url='postgresql+psycopg://', literal_binds=True, **options)
else:
    context.configure(connection=config.attributes['connection'], **options)
with context.begin_transaction():
    context.run_migrations()
'''
MIGRATION = '''from alembic import op
import sqlalchemy as sa
revision = 'p20b_expand_01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('formularios', sa.Column('p20_b_probe', sa.String(64), nullable=True), schema='public')

def downgrade():
    raise RuntimeError('P20 B does not allow downgrade; roll back services only')
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def validate_target(env, identifier, host):
    lab = env.get('P20_RUN_ID', '')
    require(bool(re.fullmatch(r'p20-[a-f0-9]{12}', lab)), 'P20_RUN_ID invalid')
    require(bool(re.fullmatch(re.escape(lab) + r'-c7-test-[0-9]{8}', identifier)), 'Only the P20 working clone is allowed')
    require(bool(re.fullmatch(re.escape(identifier) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Host must identify the exact clone')
    require(env.get('DATABASE_HOST') == host and env.get('DATABASE_NAME') == 'sagrilaft', 'Connection differs from approved clone')
    require(env.get('RUN_MODE') == 'p20-b-migration' and env.get('ZOHO_SIGN_ENABLED') == 'false', 'Unexpected runtime/Zoho mode')
    if env.get('DATABASE_URL'):
        url = urlsplit(env['DATABASE_URL'])
        require(url.hostname == host and url.path == '/sagrilaft' and url.port in (None, 5432), 'DATABASE_URL differs from clone')


def run_alembic(connection=None, offline=False):
    from alembic import command
    from alembic.config import Config
    with tempfile.TemporaryDirectory(prefix='p20-b-alembic-') as folder:
        root = Path(folder)
        (root / 'versions').mkdir()
        (root / 'env.py').write_text(ENVIRONMENT)
        (root / 'versions' / 'p20b_expand_01.py').write_text(MIGRATION)
        config = Config()
        config.set_main_option('script_location', str(root))
        config.attributes['connection'] = connection
        command.upgrade(config, REVISION, sql=offline)


def apply_connection(connection):
    """Called inside one transaction; guard baseline, refuse implicit retries."""
    import sqlalchemy as sa
    scalar = lambda query: connection.execute(sa.text(query)).scalar_one()
    require(connection.dialect.name == 'postgresql', 'PostgreSQL required')
    connection.exec_driver_sql("SET LOCAL lock_timeout = '2s'")
    connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
    require(connection.execute(sa.text('SELECT version_num FROM public.alembic_version')).scalars().all() == ['c7a1c1a65662'], 'Main revision must be c7; no automatic migration')
    require(scalar("SELECT to_regclass('public.p20_b_alembic_version') IS NULL"), 'B marker already exists; reconcile instead of retrying')
    require(scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='formularios' AND column_name='p20_b_probe'") == 0, 'B column already exists; reconcile')
    run_alembic(connection)
    require(scalar('SELECT version_num FROM public.p20_b_alembic_version') == REVISION, 'B fixture revision not verified')
    require(scalar("SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='formularios' AND column_name='p20_b_probe'") == 'YES', 'B column must be nullable')
    require(scalar('SELECT version_num FROM public.alembic_version') == 'c7a1c1a65662', 'Main Alembic revision changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-identifier', required=True)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--ssl-root-cert')
    parser.add_argument('--apply', action='store_true', help='Writes only after separately approved ECS execution; default emits offline SQL')
    args = parser.parse_args()
    try:
        validate_target(os.environ, args.db_identifier, args.expected_host)
        if not args.apply:
            run_alembic(offline=True)
            return 0
        require(args.ssl_root_cert and Path(args.ssl_root_cert).is_file(), 'RDS trust anchor required')
        import sqlalchemy as sa
        url = sa.URL.create('postgresql+psycopg', username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=args.expected_host, port=5432, database='sagrilaft')
        engine = sa.create_engine(url, poolclass=sa.pool.NullPool, connect_args={'sslmode': 'verify-full', 'sslrootcert': args.ssl_root_cert, 'connect_timeout': 10})
        try:
            with engine.begin() as connection:
                require(connection.execute(sa.text('SELECT current_database()')).scalar_one() == 'sagrilaft', 'Wrong database')
                require(connection.execute(sa.text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar_one() is True, 'TLS required')
                apply_connection(connection)
        finally:
            engine.dispose()
        print(json.dumps({'event': 'p20_b_expansion_verified', 'mainRevision': 'c7a1c1a65662', 'fixtureRevision': REVISION, 'column': COLUMN, 'nullable': True, 'activationAllowed': False}), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'event': 'p20_b_expansion_blocked', 'exceptionType': type(exc).__name__, 'retryAllowed': False}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
