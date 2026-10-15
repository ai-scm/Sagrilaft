"""Real PostgreSQL checks, only against an explicitly created /tmp Unix socket."""
import os
from pathlib import Path
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from test_p20_b_preparation import migration


@pytest.fixture
def local_engine():
    socket = os.environ.get('P20_B_LOCAL_PG_SOCKET')
    if not socket:
        pytest.skip('Explicit isolated local PostgreSQL socket required')
    socket_path = Path(socket).resolve()
    assert str(socket_path).startswith('/tmp/p20-b-pg-') and socket_path.is_dir()
    assert (socket_path / 'data' / 'PG_VERSION').is_file()
    admin_url = sa.URL.create('postgresql+psycopg', username='p20_b_local', database='postgres', query={'host': str(socket_path), 'port': '55481'})
    admin = sa.create_engine(admin_url, isolation_level='AUTOCOMMIT')
    name = 'p20_b_' + uuid.uuid4().hex
    with admin.connect() as c: c.exec_driver_sql('CREATE DATABASE ' + name)
    engine = sa.create_engine(admin_url.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c: c.exec_driver_sql('DROP DATABASE ' + name)
        admin.dispose()


def seed_baseline(engine):
    # This setup tests the existing ORM, not a claim to reconstruct the complete RDS.
    from infrastructure.persistencia.database import Base
    from infrastructure.persistencia.models import Formulario
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY)')
        c.exec_driver_sql("INSERT INTO public.alembic_version VALUES ('c7a1c1a65662')")
    with Session(engine) as session:
        session.add(Formulario(id='P20-LOCAL-B', razon_social='P20 sintético local B', ciudad='antes'))
        session.commit()
    return Formulario


def test_additive_migration_preserves_old_orm_reads_writes_and_schema_on_retry(local_engine):
    Formulario = seed_baseline(local_engine)
    with local_engine.begin() as c: migration.apply_connection(c)
    with local_engine.begin() as c:
        assert c.exec_driver_sql('SELECT version_num FROM public.alembic_version').scalar_one() == 'c7a1c1a65662'
        assert c.exec_driver_sql('SELECT version_num FROM public.p20_b_alembic_version').scalar_one() == 'p20b_expand_01'
        c.exec_driver_sql("UPDATE public.formularios SET p20_b_probe='P20-B-control' WHERE id='P20-LOCAL-B'")
    with Session(local_engine) as session:
        row = session.get(Formulario, 'P20-LOCAL-B')
        assert row.ciudad == 'antes'
        row.ciudad = 'después con código anterior'
        session.commit()
        assert session.get(Formulario, 'P20-LOCAL-B').ciudad == 'después con código anterior'
    with local_engine.connect() as c:
        assert c.exec_driver_sql("SELECT p20_b_probe FROM public.formularios WHERE id='P20-LOCAL-B'").scalar_one() == 'P20-B-control'
    with pytest.raises(RuntimeError, match='already exists'):
        with local_engine.begin() as c: migration.apply_connection(c)
    with local_engine.connect() as c:
        assert c.exec_driver_sql('SELECT version_num FROM public.p20_b_alembic_version').scalar_one() == 'p20b_expand_01'


def test_failed_outer_transaction_rolls_back_fixture_ddl_and_marker(local_engine):
    seed_baseline(local_engine)
    with pytest.raises(RuntimeError, match='local rollback check'):
        with local_engine.begin() as c:
            migration.apply_connection(c)
            raise RuntimeError('local rollback check')
    with local_engine.connect() as c:
        assert c.exec_driver_sql("SELECT to_regclass('public.p20_b_alembic_version')").scalar_one() is None
        assert c.exec_driver_sql("SELECT count(*) FROM information_schema.columns WHERE table_name='formularios' AND column_name='p20_b_probe'").scalar_one() == 0
        assert c.exec_driver_sql('SELECT version_num FROM public.alembic_version').scalar_one() == 'c7a1c1a65662'


def test_wrong_main_revision_is_rejected_before_fixture_ddl(local_engine):
    seed_baseline(local_engine)
    with local_engine.begin() as c: c.exec_driver_sql("UPDATE public.alembic_version SET version_num='f8a9b0c1d2e3'")
    with pytest.raises(RuntimeError, match='Main revision'):
        with local_engine.begin() as c: migration.apply_connection(c)
    with local_engine.connect() as c:
        assert c.exec_driver_sql("SELECT to_regclass('public.p20_b_alembic_version')").scalar_one() is None
