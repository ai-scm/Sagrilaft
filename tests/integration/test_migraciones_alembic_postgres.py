import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text, pool
from sqlalchemy.engine import make_url


pytestmark = pytest.mark.integration

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
BACKEND_DIR = RAIZ_PROYECTO / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _config_alembic() -> Config:
    return Config(str(ALEMBIC_INI))


def _url_admin_postgres() -> str:
    url = os.getenv("TEST_POSTGRES_ADMIN_URL") or os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip(
            "Defina TEST_POSTGRES_ADMIN_URL para validar migraciones contra PostgreSQL real."
        )

    parsed = make_url(url)
    maintenance_db = os.getenv("TEST_POSTGRES_MAINTENANCE_DB", "postgres")
    return parsed.set(database=maintenance_db).render_as_string(hide_password=False)


def _crear_base_temporal(admin_url: str) -> tuple[str, str]:
    nombre_bd = f"sagrilaft_alembic_test_{uuid.uuid4().hex}"
    temp_url = make_url(admin_url).set(database=nombre_bd)
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conexion:
        expected = os.getenv("TEST_POSTGRES_EXPECTED_MAJOR")
        if expected:
            actual = int(conexion.execute(text("SHOW server_version_num")).scalar_one()) // 10000
            assert actual == int(expected), f"Expected PostgreSQL {expected}, got {actual}"
        conexion.execute(text(f'CREATE DATABASE "{nombre_bd}"'))

    engine.dispose()
    return nombre_bd, temp_url.render_as_string(hide_password=False)


def _eliminar_base_temporal(admin_url: str, nombre_bd: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conexion:
        conexion.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :nombre_bd AND pid <> pg_backend_pid()
                """
            ),
            {"nombre_bd": nombre_bd},
        )
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre_bd}"'))
    engine.dispose()


def _columnas(inspector, tabla: str) -> dict[str, dict]:
    return {columna["name"]: columna for columna in inspector.get_columns(tabla)}


def _insertar_acceso_prueba(connection, correo):
    connection.execute(text("INSERT INTO formularios (id) VALUES ('PHASE3')"))
    connection.execute(text("""
        INSERT INTO accesos_manuales
        (id, pin_hash, token_diligenciamiento, correo_destinatario, razon_social,
         tipo_contraparte, area_responsable, formulario_id, expires_at)
        VALUES ('PHASE3', 'hash-sintetico', 'token-sintetico', :correo, 'Prueba',
                'proveedor', 'pruebas', 'PHASE3', CURRENT_TIMESTAMP)
    """), {"correo": correo})


@pytest.fixture
def bd_migracion_guard(monkeypatch):
    """Cada caso usa una BD nueva; no reutiliza tablas de una BD existente."""
    admin = _url_admin_postgres()
    name, url = _crear_base_temporal(admin)
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        yield engine
    finally:
        engine.dispose()
        _eliminar_base_temporal(admin, name)


def test_bloqueo_impide_segunda_migracion_y_libera_tras_error(bd_migracion_guard, monkeypatch):
    from infrastructure.persistencia.migration_guard import migration_lock

    monkeypatch.setenv("MIGRATION_LOCK_TIMEOUT_SECONDS", "0")
    with bd_migracion_guard.connect() as first, bd_migracion_guard.connect() as second:
        with pytest.raises(ValueError, match="fallo simulado"):
            with migration_lock(first):
                first.execute(text("SELECT 1"))
                first.commit()  # El lock debe sobrevivir commits de la migración.
                with pytest.raises(TimeoutError):
                    with migration_lock(second):
                        pytest.fail("Dos migraciones entraron simultáneamente")
                raise ValueError("fallo simulado")
        with migration_lock(second):
            assert second.execute(text("SELECT 1")).scalar_one() == 1


def test_lock_espera_limitada_y_liberacion_tras_error_sql(bd_migracion_guard, monkeypatch):
    import time
    from sqlalchemy.exc import DBAPIError
    from infrastructure.persistencia.migration_guard import migration_lock

    monkeypatch.setenv("MIGRATION_LOCK_TIMEOUT_SECONDS", "1")
    with bd_migracion_guard.connect() as first, bd_migracion_guard.connect() as second:
        with pytest.raises(DBAPIError):
            with migration_lock(first):
                start = time.monotonic()
                with pytest.raises(TimeoutError):
                    with migration_lock(second):
                        pytest.fail("El segundo migrador no debe entrar")
                assert time.monotonic() - start >= 1
                first.execute(text("SELECT 1 / 0"))  # Transacción PostgreSQL abortada.
        with migration_lock(second):
            assert second.execute(text("SELECT 1")).scalar_one() == 1


def test_verificacion_no_admite_sql_offline(monkeypatch):
    monkeypatch.setenv("MIGRATION_VERIFY_HEAD", "1")
    with pytest.raises(RuntimeError, match="no admite --sql"):
        command.upgrade(_config_alembic(), "head", sql=True)


@pytest.mark.parametrize("timeout", ["-1", "3601", "abc"])
def test_timeout_de_lock_invalido(bd_migracion_guard, monkeypatch, timeout):
    from infrastructure.persistencia.migration_guard import migration_lock

    monkeypatch.setenv("MIGRATION_LOCK_TIMEOUT_SECONDS", timeout)
    with bd_migracion_guard.connect() as connection:
        with pytest.raises(RuntimeError, match="MIGRATION_LOCK_TIMEOUT_SECONDS"):
            with migration_lock(connection):
                pytest.fail("Timeout inválido aceptado")


def test_alembic_respeta_lock_antes_de_crear_esquema(bd_migracion_guard, monkeypatch):
    from infrastructure.persistencia.migration_guard import migration_lock

    monkeypatch.setenv("MIGRATION_LOCK_TIMEOUT_SECONDS", "0")
    with bd_migracion_guard.connect() as owner:
        with migration_lock(owner):
            with pytest.raises(TimeoutError):
                command.upgrade(_config_alembic(), "head")
            assert not inspect(owner).has_table("alembic_version")
    # Tras liberar el lock, el mismo comando debe poder completar y confirmar.
    monkeypatch.setenv("MIGRATION_VERIFY_HEAD", "1")
    command.upgrade(_config_alembic(), "head")
    with bd_migracion_guard.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "f8a9b0c1d2e3"


def test_verificacion_rechaza_revision_final_distinta_y_revierte(bd_migracion_guard, monkeypatch, capsys):
    monkeypatch.setenv("MIGRATION_VERIFY_HEAD", "1")
    with pytest.raises(RuntimeError, match="inesperada"):
        command.upgrade(_config_alembic(), "c7a1c1a65662")
    assert "migration_schema_verified" not in capsys.readouterr().out
    with bd_migracion_guard.connect() as connection:
        assert not inspect(connection).has_table("formularios")


def test_upgrade_verificado_con_datos_y_segunda_ejecucion(bd_migracion_guard, monkeypatch, capsys):
    command.upgrade(_config_alembic(), "c7a1c1a65662")
    with bd_migracion_guard.begin() as connection:
        _insertar_acceso_prueba(connection, "prueba@example.invalid")
    monkeypatch.setenv("MIGRATION_VERIFY_HEAD", "1")
    command.upgrade(_config_alembic(), "head")
    output = capsys.readouterr().out
    assert '"migration_before"' in output and '"c7a1c1a65662"' in output
    assert '"migration_schema_verified"' in output
    with bd_migracion_guard.connect() as connection:
        assert connection.execute(text("SELECT correo_destinatario FROM accesos_manuales WHERE id='PHASE3'")).scalar_one() == "prueba@example.invalid"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "f8a9b0c1d2e3"
    command.upgrade(_config_alembic(), "head")
    assert '"migration_schema_verified"' in capsys.readouterr().out


def test_upgrade_fallido_no_reporta_exito_y_permite_reintento(bd_migracion_guard, monkeypatch, capsys):
    from sqlalchemy.exc import IntegrityError

    command.upgrade(_config_alembic(), "c7a1c1a65662")
    with bd_migracion_guard.begin() as connection:
        _insertar_acceso_prueba(connection, None)
    monkeypatch.setenv("MIGRATION_VERIFY_HEAD", "1")
    with pytest.raises(IntegrityError):
        command.upgrade(_config_alembic(), "head")
    assert "migration_schema_verified" not in capsys.readouterr().out
    with bd_migracion_guard.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "c7a1c1a65662"
        connection.execute(text("UPDATE accesos_manuales SET correo_destinatario='prueba@example.invalid' WHERE id='PHASE3'"))
    command.upgrade(_config_alembic(), "head")
    assert '"migration_schema_verified"' in capsys.readouterr().out


def test_alembic_tiene_un_solo_head():
    script = ScriptDirectory.from_config(_config_alembic())

    assert script.get_heads() == [script.get_current_head()]


def test_alembic_upgrade_head_crea_esquema_postgresql(monkeypatch):
    admin_url = _url_admin_postgres()
    nombre_bd, database_url = _crear_base_temporal(admin_url)

    try:
        monkeypatch.setenv("DATABASE_URL", database_url)
        command.upgrade(_config_alembic(), "head")

        engine = create_engine(database_url)
        inspector = inspect(engine)
        tablas = set(inspector.get_table_names())

        assert {
            "formularios",
            "accesos_manuales",
            "documentos_adjuntos",
            "eventos_formulario",
            "formulario_alertas_inconsistencia",
            "alembic_version",
        }.issubset(tablas)

        with engine.connect() as conexion:
            version = conexion.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            trigger = conexion.execute(
                text(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE tgname = 'tg_audit_estado'
                    """
                )
            ).scalar_one_or_none()

        assert version == ScriptDirectory.from_config(_config_alembic()).get_current_head()
        assert trigger == "tg_audit_estado"

        columnas_formularios = _columnas(inspector, "formularios")
        assert "numero_correccion" in columnas_formularios
        assert "zoho_request_id" in columnas_formularios
        assert "ruta_documento_firmado" in columnas_formularios
        assert "sagrilaft_reporte_id" in columnas_formularios

        columnas_accesos = _columnas(inspector, "accesos_manuales")
        assert columnas_accesos["correo_destinatario"]["nullable"] is False
        assert "ultimo_envio_correo" in columnas_accesos

        columnas_documentos = _columnas(inspector, "documentos_adjuntos")
        assert "version_numero" in columnas_documentos
        assert "version_anterior_id" in columnas_documentos
        assert "hash_sha256" in columnas_documentos
        assert "snapshot_datos" in columnas_documentos

        engine.dispose()
    finally:
        _eliminar_base_temporal(admin_url, nombre_bd)


def test_las_28_revisiones_desde_cero_y_head_idempotente(bd_migracion_guard, monkeypatch):
    """Execute every revision, including both branches and their merge."""
    script = ScriptDirectory.from_config(_config_alembic())
    revisions = list(reversed(list(script.walk_revisions())))
    assert len(revisions) == 28
    assert script.get_heads() == ['f8a9b0c1d2e3']
    for revision in revisions:
        command.upgrade(_config_alembic(), revision.revision)
    monkeypatch.setenv('MIGRATION_VERIFY_HEAD', '1')
    command.upgrade(_config_alembic(), 'head')
    before = inspect(bd_migracion_guard).get_table_names()
    command.upgrade(_config_alembic(), 'head')
    assert inspect(bd_migracion_guard).get_table_names() == before
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == script.get_current_head()


@pytest.mark.parametrize('branch', ['d4e5f6a7b8c9', 'f1a2b3c4d5e6'])
def test_actualizacion_desde_cada_rama_preserva_fila(bd_migracion_guard, branch):
    command.upgrade(_config_alembic(), branch)
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id, razon_social) VALUES ('rama', 'Empresa sintética')"))
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text("SELECT razon_social FROM formularios WHERE id='rama'")).scalar_one() == 'Empresa sintética'
        columns = _columnas(inspect(conn), 'formularios')
        assert {'numero_correccion', 'pais_funciones', 'departamento_funciones'} <= set(columns)


def test_conversiones_y_normalizacion_con_datos_representativos(bd_migracion_guard):
    from datetime import date
    from decimal import Decimal

    command.upgrade(_config_alembic(), 'c8d9e0f1a2b3')
    dates = [('2024-02-29', date(2024, 2, 29)), (' 2-ENE-2000 ', date(2000, 1, 2)),
             ('2023-02-29', None), ('texto inválido', None), ('', None), (None, None)]
    flags = [('sí', True), (' SI ', True), ('true', True), ('1', True), ('no', False),
             ('0', False), (None, False), ('desconocido', False)]
    with bd_migracion_guard.begin() as conn:
        for i, (raw, _) in enumerate(dates):
            conn.execute(text('''INSERT INTO formularios
                (id, tipo_persona, fecha_nacimiento, fecha_expedicion, ingresos_mensuales,
                 direccion_residencia, ciudad_residencia)
                VALUES (:id, 'natural', :fecha, :fecha, 1234.567, 'Calle sintética', 'Bogotá')'''),
                {'id': f'date{i}', 'fecha': raw})
        for i, (raw, _) in enumerate(flags):
            conn.execute(text('''INSERT INTO formularios
                (id, tipo_persona, autorretenedor, realiza_operaciones_moneda_extranjera,
                 actividad_clasificacion, total_activos)
                VALUES (:id, 'juridica', :flag, :flag, 'servicios', 0)'''), {'id': f'flag{i}', 'flag': raw})
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        for i, (_, expected) in enumerate(dates):
            row = conn.execute(text('SELECT fecha_nacimiento, fecha_expedicion, ingresos_mensuales FROM formularios WHERE id=:id'), {'id': f'date{i}'}).one()
            assert row == (expected, expected, Decimal('1234.57'))
            assert conn.execute(text('SELECT ciudad_residencia FROM formulario_persona_natural WHERE formulario_id=:id'), {'id': f'date{i}'}).scalar_one() == 'Bogotá'
        for i, (_, expected) in enumerate(flags):
            row = conn.execute(text('''SELECT f.realiza_operaciones_moneda_extranjera, c.autorretenedor, c.actividad_clasificacion
                FROM formularios f JOIN formulario_clasificacion_tributaria c ON c.formulario_id=f.id WHERE f.id=:id'''), {'id': f'flag{i}'}).one()
            assert row == (expected, expected, 'servicios')
        assert conn.execute(text("SELECT to_regprocedure('_sagrilaft_parse_fecha_colombia(text)')")).scalar_one() is None


@pytest.mark.parametrize('column,value', [('digito_verificacion', 'XX'), ('dia_firma', 32),
    ('mes_firma', 0), ('year_firma', 1999)])
def test_check_rechaza_datos_previos_invalidos_sin_avanzar_revision(bd_migracion_guard, column, value):
    from sqlalchemy.exc import IntegrityError
    command.upgrade(_config_alembic(), 'a2b3c4d5e6f7')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text(f'INSERT INTO formularios(id, {column}) VALUES (:id, :value)'), {'id': 'invalid', 'value': value})
    with pytest.raises(IntegrityError):
        command.upgrade(_config_alembic(), 'b3c4d5e6f7a8')
    with bd_migracion_guard.begin() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'a2b3c4d5e6f7'
        conn.execute(text(f'UPDATE formularios SET {column}=NULL'))
    command.upgrade(_config_alembic(), 'head')


def test_numeric_fuera_de_rango_detiene_y_preserva_revision(bd_migracion_guard):
    from sqlalchemy.exc import DataError
    command.upgrade(_config_alembic(), 'c8d9e0f1a2b3')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id,total_activos) VALUES ('overflow',1e20)"))
    with pytest.raises(DataError):
        command.upgrade(_config_alembic(), 'e9f0a1b2c3d4')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'c8d9e0f1a2b3'


@pytest.mark.parametrize('legacy', ['absent', 'old', 'both'])
def test_snapshot_puente_preserva_json_y_no_sobrescribe_actual(bd_migracion_guard, legacy):
    command.upgrade(_config_alembic(), 'd5e6f7a8b9c0')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id) VALUES ('snapshot')"))
        conn.execute(text("""INSERT INTO documentos_adjuntos(id,formulario_id,tipo_documento,nombre_archivo,ruta_archivo)
            VALUES ('doc','snapshot','prueba','sintetico.pdf','/no-existe.pdf')"""))
        if legacy in ('old', 'both'):
            conn.execute(text('ALTER TABLE documentos_adjuntos ADD COLUMN datos_snapshot TEXT'))
            conn.execute(text('UPDATE documentos_adjuntos SET datos_snapshot=:json'), {'json': '{"original":true}'})
        if legacy == 'both':
            conn.execute(text('ALTER TABLE documentos_adjuntos ADD COLUMN snapshot_datos TEXT'))
            conn.execute(text('UPDATE documentos_adjuntos SET snapshot_datos=:json'), {'json': '{"actual":true}'})
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        expected = {'absent': None, 'old': '{"original":true}', 'both': '{"actual":true}'}[legacy]
        assert conn.execute(text('SELECT snapshot_datos FROM documentos_adjuntos')).scalar_one() == expected
        assert 'datos_snapshot' not in _columnas(inspect(conn), 'documentos_adjuntos')
        assert conn.execute(text('SELECT version_numero FROM documentos_adjuntos')).scalar_one() == 1


def test_trigger_indices_y_cascada_en_head(bd_migracion_guard):
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id,estado) VALUES ('audit','BORRADOR')"))
        conn.execute(text("UPDATE formularios SET estado='ENVIADO' WHERE id='audit'"))
        assert conn.execute(text("SELECT estado_anterior,estado_nuevo FROM eventos_formulario WHERE formulario_id='audit'")).one() == ('BORRADOR', 'ENVIADO')
        conn.execute(text("SET LOCAL sagrilaft.from_app='1'"))
        conn.execute(text("UPDATE formularios SET estado='APROBADO' WHERE id='audit'"))
        assert conn.execute(text("SELECT count(*) FROM eventos_formulario WHERE formulario_id='audit'")).scalar_one() == 1
        conn.execute(text("INSERT INTO formulario_persona_natural(formulario_id,ciudad_residencia) VALUES ('audit','Bogotá')"))
        conn.execute(text("DELETE FROM formularios WHERE id='audit'"))
        assert conn.execute(text('SELECT count(*) FROM formulario_persona_natural')).scalar_one() == 0
        assert conn.execute(text('SELECT count(*) FROM eventos_formulario')).scalar_one() == 0
        assert 'ix_eventos_formulario_form_created' in {idx['name'] for idx in inspect(conn).get_indexes('eventos_formulario')}


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='Histórica c3f1a2b4d5e6 elimina fecha_firma sin backfill; requiere decisión sobre datos existentes')
def test_preservacion_fecha_firma_historica(bd_migracion_guard):
    command.upgrade(_config_alembic(), 'ed8fe2b9a6b2')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id,fecha_firma) VALUES ('firma','2024-02-29')"))
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text("SELECT dia_firma,mes_firma,year_firma FROM formularios WHERE id='firma'")).one() == (29, 2, 2024)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='Histórica c8d9e0f1a2b3 elimina contactos sin copiarlos; no es un fallo específico de PG16')
def test_preservacion_contactos_historicos(bd_migracion_guard):
    command.upgrade(_config_alembic(), 'b7e4f2a19c3d')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text("INSERT INTO formularios(id,contacto_ordenes_nombre) VALUES ('contact','Contacto sintético')"))
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM contactos WHERE formulario_id='contact'")).scalar_one() == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='Histórica b7e4f2a19c3d elimina listas sin copiarlas; no se certifica conservación de datos')
def test_preservacion_listas_historicas(bd_migracion_guard):
    command.upgrade(_config_alembic(), 'd62426367da1')
    with bd_migracion_guard.begin() as conn:
        conn.execute(text('INSERT INTO formularios(id,accionistas) VALUES (:id,:lista)'),
                     {'id': 'lista', 'lista': '[{"nombre":"Accionista sintético","porcentaje":50}]'})
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM formulario_accionistas WHERE formulario_id='lista'")).scalar_one() == 1


@pytest.fixture
def esquema_actual(bd_migracion_guard, monkeypatch):
    """Schema comes only from Alembic, never metadata.create_all()."""
    monkeypatch.setenv('MIGRATION_VERIFY_HEAD', '1')
    command.upgrade(_config_alembic(), 'head')
    with bd_migracion_guard.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'f8a9b0c1d2e3'
    return bd_migracion_guard


def test_head_contiene_todas_las_tablas_y_columnas_del_orm_actual(esquema_actual):
    from infrastructure.persistencia.models import Base
    inspector = inspect(esquema_actual)
    tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        assert table.name in tables, f'Missing table: {table.name}'
        actual = set(_columnas(inspector, table.name))
        assert set(table.columns.keys()) <= actual, f'Missing columns in {table.name}: {set(table.columns.keys()) - actual}'
    assert not {'fecha_firma', 'nombre_firma'} & set(_columnas(inspector, 'formularios'))


def test_repositorios_firma_crear_leer_actualizar_en_head(esquema_actual):
    from sqlalchemy.orm import Session
    from infrastructure.persistencia.repositorios.formulario import RepositorioFormularioSQLAlchemy
    from infrastructure.persistencia.repositorios.firma import RepositorioFirmaSQLAlchemy

    with Session(esquema_actual) as session:
        created = RepositorioFormularioSQLAlchemy(session).crear({
            'tipo_persona': 'juridica', 'nombre_representante': 'Firmante sintético',
            'dia_firma': 29, 'mes_firma': 2, 'year_firma': 2024, 'ciudad_firma': 'Bogotá'})
        identifier = created.id
    # New sessions ensure reads hit persisted data, not a previous identity map.
    with Session(esquema_actual) as session:
        repo = RepositorioFirmaSQLAlchemy(session)
        actual = repo.obtener_formulario(identifier, bloquear=True)
        assert (actual.dia_firma, actual.mes_firma, actual.year_firma) == (29, 2, 2024)
        assert actual.nombre_representante == 'Firmante sintético'
        repo.actualizar_formulario(identifier, {'dia_firma': 6, 'mes_firma': 10, 'year_firma': 2026,
            'ciudad_firma': 'Medellín', 'zoho_request_id': 'simulado-sin-llamada-externa',
            'ruta_documento_firmado': '/sintetico/firmado.pdf'})
    with Session(esquema_actual) as session:
        actual = RepositorioFirmaSQLAlchemy(session).obtener_formulario_por_zoho_id('simulado-sin-llamada-externa')
        assert actual.id == identifier
        assert (actual.dia_firma, actual.mes_firma, actual.year_firma, actual.ciudad_firma) == (6, 10, 2026, 'Medellín')
        assert actual.ruta_documento_firmado == '/sintetico/firmado.pdf'
        assert RepositorioFormularioSQLAlchemy(session).obtener_por_id(identifier).dia_firma == 6


@pytest.mark.parametrize('tipo', ['ordenes', 'pagos'])
def test_repositorio_contactos_crear_leer_actualizar_en_head(esquema_actual, tipo):
    from sqlalchemy.orm import Session
    from infrastructure.persistencia.repositorios.formulario import RepositorioFormularioSQLAlchemy

    initial = {f'contacto_{kind}_{field}': value for kind in ('ordenes', 'pagos')
               for field, value in {'nombre': f'Contacto {kind}', 'cargo': 'Analista',
                                    'telefono': '3000000000', 'correo': f'{kind}@example.invalid'}.items()}
    with Session(esquema_actual) as session:
        identifier = RepositorioFormularioSQLAlchemy(session).crear({'tipo_persona': 'juridica', **initial}).id
    changes = {f'contacto_{tipo}_{field}': value for field, value in
               {'nombre': 'Contacto actualizado', 'cargo': 'Coordinador', 'telefono': '3111111111',
                'correo': 'nuevo@example.invalid'}.items()}
    with Session(esquema_actual) as session:
        repo = RepositorioFormularioSQLAlchemy(session)
        actual = repo.obtener_por_id(identifier)
        assert all(getattr(actual, key) == value for key, value in initial.items())
        repo.actualizar(identifier, changes)
    with Session(esquema_actual) as session:
        actual = RepositorioFormularioSQLAlchemy(session).obtener_por_codigo(identifier)
        assert all(getattr(actual, key) == value for key, value in {**initial, **changes}.items())
        assert session.execute(text('SELECT count(*) FROM contactos WHERE formulario_id=:id'), {'id': identifier}).scalar_one() == 2


_LISTAS_REPOSITORIO = [
    ('junta_directiva', 'formulario_junta_directiva', {'cargo': 'Director', 'nombre': 'Persona', 'tipo_id': 'CC', 'numero_id': '123', 'es_pep': 'no', 'vinculos_pep': 'no'}),
    ('accionistas', 'formulario_accionistas', {'nombre': 'Persona', 'tipo_id': 'CC', 'numero_id': '123', 'es_pep': 'no', 'vinculos_pep': 'no', 'porcentaje': 50.0}),
    ('beneficiario_final', 'formulario_beneficiarios_finales', {'nombre': 'Persona', 'tipo_id': 'CC', 'numero_id': '123', 'es_pep': 'no', 'vinculos_pep': 'no', 'porcentaje': 50.0}),
    ('referencias_comerciales', 'formulario_referencias_comerciales', {'nombre_establecimiento': 'Empresa', 'persona_contacto': 'Persona', 'telefono': '3000000000', 'ciudad': 'Bogotá'}),
    ('referencias_bancarias', 'formulario_referencias_bancarias_declaradas', {'entidad': 'Banco sintético', 'producto': 'Ahorros'}),
    ('informacion_bancaria_pagos', 'formulario_cuentas_pago', {'entidad_bancaria': 'Banco sintético', 'ciudad_oficina': 'Bogotá', 'tipo_cuenta': 'Ahorros', 'numero_cuenta': '000123'}),
    ('tipos_transaccion', 'formulario_tipos_transaccion', 'importaciones'),
]


@pytest.mark.parametrize('field,table,item', _LISTAS_REPOSITORIO, ids=[x[0] for x in _LISTAS_REPOSITORIO])
def test_repositorio_listas_crear_leer_reemplazar_y_vaciar_en_head(esquema_actual, field, table, item):
    from sqlalchemy.orm import Session
    from infrastructure.persistencia.repositorios.formulario import RepositorioFormularioSQLAlchemy

    # Populate every collection together; changing one must preserve all others.
    initial = {name: [entry] for name, _, entry in _LISTAS_REPOSITORIO}
    with Session(esquema_actual) as session:
        identifier = RepositorioFormularioSQLAlchemy(session).crear({'tipo_persona': 'juridica', **initial}).id
    if isinstance(item, str):
        changed = 'exportaciones'
    else:
        changed = dict(item)
        first_field = next(iter(item))
        changed[first_field] = item[first_field] + ' actualizado'
        if 'porcentaje' in changed:
            changed['porcentaje'] = 25.0
    with Session(esquema_actual) as session:
        repo = RepositorioFormularioSQLAlchemy(session)
        actual = repo.obtener_por_id(identifier)
        assert all(getattr(actual, key) == value for key, value in initial.items())
        repo.actualizar(identifier, {field: [changed, item]})
    with Session(esquema_actual) as session:
        repo = RepositorioFormularioSQLAlchemy(session)
        actual = repo.obtener_por_codigo(identifier)
        # Transaction types are a set-like collection; other lists preserve order.
        if field == 'tipos_transaccion':
            assert set(actual.tipos_transaccion) == {changed, item}
        else:
            assert getattr(actual, field) == [changed, item]
        assert all(getattr(actual, key) == value for key, value in initial.items() if key != field)
        assert session.execute(text(f'SELECT count(*) FROM {table} WHERE formulario_id=:id'), {'id': identifier}).scalar_one() == 2
        repo.actualizar(identifier, {field: []})
    with Session(esquema_actual) as session:
        actual = RepositorioFormularioSQLAlchemy(session).obtener_por_id(identifier)
        assert getattr(actual, field) == []
        assert all(getattr(actual, key) == value for key, value in initial.items() if key != field)
        assert session.execute(text(f'SELECT count(*) FROM {table} WHERE formulario_id=:id'), {'id': identifier}).scalar_one() == 0
