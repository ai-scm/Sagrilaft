#!/usr/bin/env python3
"""One-shot P20-C role provisioning; credentials come only from ECS secret injection."""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets

LAB = 'p20-9c67b6ea6842'
DB_ID = LAB + '-c7-test-20261012'
DB_HOST = DB_ID + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
DB_NAME = 'sagrilaft'
ADMIN_USER = 'sagrilaft_user'
INVENTORY_USER = 'p20_c_inventory'
FORM_ID = '73bf8b16-9551-4656-965d-518afc19d7d1'
MARKER = 'P20-9c67b6ea6842-SMOKE-20261014T013047Z-0fd1ff'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def validate_environment(env):
    require(env.get('P20_RUN_ID') == LAB and env.get('RUN_MODE') == 'p20-c-provisioner'
            and env.get('ZOHO_SIGN_ENABLED') == 'false', 'Wrong P20 runtime')
    require(env.get('EXPECTED_DB_IDENTIFIER') == DB_ID
            and env.get('DATABASE_HOST') == DB_HOST
            and env.get('DATABASE_NAME') == DB_NAME, 'Database target is not the approved clone')
    require('DATABASE_URL' not in env, 'DATABASE_URL is forbidden')
    require(env.get('DB_ADMIN_USER') == ADMIN_USER
            and env.get('EXPECTED_DB_ADMIN_USER') == ADMIN_USER, 'Unexpected database administrator')
    require(env.get('INVENTORY_DB_USER') == INVENTORY_USER, 'Unexpected inventory role')
    require(bool(env.get('DB_ADMIN_PASSWORD')) and bool(env.get('INVENTORY_DB_PASSWORD')),
            'Credentials must be injected from Secrets Manager')
    require(bool(re.fullmatch(r'[A-Za-z0-9]{32}', env['INVENTORY_DB_PASSWORD'])),
            'Inventory password does not match the generated secret policy')


def scram_verifier(password, salt=None, iterations=4096):
    """Return a PostgreSQL SCRAM-SHA-256 verifier so plaintext is not sent as SQL."""
    require(bool(re.fullmatch(r'[A-Za-z0-9]{32}', password)), 'Unexpected generated password format')
    require(4096 <= iterations <= 1000000, 'SCRAM iteration count outside safe bounds')
    salt = salt or secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=32)
    client_key = hmac.new(salted, b'Client Key', hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b'Server Key', hashlib.sha256).digest()
    enc = lambda value: base64.b64encode(value).decode('ascii')
    return f'SCRAM-SHA-256${iterations}:{enc(salt)}${enc(stored_key)}:{enc(server_key)}'


def provision_role(connection, admin_user, inventory_user, password):
    """Create the least-privilege login and grants in one transaction; fail if it exists."""
    from psycopg import sql
    require(connection.execute('SELECT current_database()').fetchone()[0] == DB_NAME,
            'Connected to a different database')
    identity = connection.execute(
        'SELECT current_user, r.rolcreaterole FROM pg_roles r WHERE r.rolname=current_user'
    ).fetchone()
    require(identity == (admin_user, True), 'Database principal lacks expected CREATEROLE capability')
    ssl = connection.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()
    require(ssl == (True,), 'TLS is not active')
    exists = connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (inventory_user,)).fetchone()
    require(exists is None, 'Inventory role already exists; reconcile it before proceeding')
    verifier = scram_verifier(password)
    connection.execute(sql.SQL(
        'CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION '
        'NOBYPASSRLS NOINHERIT PASSWORD {}'
    ).format(sql.Identifier(inventory_user), sql.Literal(verifier)))
    connection.execute(sql.SQL('ALTER ROLE {} SET default_transaction_read_only=on')
                        .format(sql.Identifier(inventory_user)))
    connection.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}')
                        .format(sql.Identifier(DB_NAME), sql.Identifier(inventory_user)))
    connection.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(inventory_user)))
    for table in ('alembic_version', 'p20_b_alembic_version'):
        connection.execute(sql.SQL('GRANT SELECT (version_num) ON TABLE public.{} TO {}')
                            .format(sql.Identifier(table), sql.Identifier(inventory_user)))
    connection.execute(sql.SQL(
        'GRANT SELECT (id, razon_social, ciudad, estado, p20_b_probe) '
        'ON TABLE public.formularios TO {}'
    ).format(sql.Identifier(inventory_user)))
    return {'role': inventory_user, 'database': DB_NAME,
            'grants': ['CONNECT:sagrilaft', 'USAGE:public', 'SELECT:approved inventory columns'],
            'passwordLogged': False}


def verify_inventory_login(env, sslrootcert):
    import psycopg
    from psycopg import sql
    with psycopg.connect(host=DB_HOST, port=5432, dbname=DB_NAME,
                         user=INVENTORY_USER, password=env['INVENTORY_DB_PASSWORD'],
                         sslmode='verify-full', sslrootcert=sslrootcert, connect_timeout=10,
                         autocommit=True, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            require(conn.execute('SELECT current_database(), current_user').fetchone() == (DB_NAME, INVENTORY_USER),
                    'Inventory login identity differs')
            require(conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone() == (True,),
                    'Inventory connection is not TLS')
            require(conn.execute('SELECT version_num FROM public.alembic_version').fetchone() == ('c7a1c1a65662',),
                    'Alembic revision differs')
            require(conn.execute('SELECT version_num FROM public.p20_b_alembic_version').fetchone() == ('p20b_expand_01',),
                    'P20-B marker differs')
            controls = conn.execute(
                'SELECT id, razon_social, ciudad, estado, p20_b_probe '
                'FROM public.formularios WHERE id=%s', (FORM_ID,)
            ).fetchone()
            require(controls is not None and controls[:4] == (FORM_ID, MARKER,
                    'P20 prueba de recuperación B', 'borrador'), 'Synthetic control row differs')
            dml = conn.execute('''SELECT
                has_table_privilege(current_user,'public.formularios','INSERT'),
                has_table_privilege(current_user,'public.formularios','UPDATE'),
                has_table_privilege(current_user,'public.formularios','DELETE'),
                has_table_privilege(current_user,'public.formularios','TRUNCATE')''').fetchone()
            require(dml == (False, False, False, False), 'Inventory role unexpectedly has DML privileges')
            return {'database': DB_NAME, 'role': INVENTORY_USER, 'tlsVerifyFull': True,
                    'mainRevision': 'c7a1c1a65662', 'bMarker': 'p20b_expand_01',
                    'syntheticControlFound': True, 'dmlPrivileges': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sentinel', choices=['P20_C_PROVISION_INVENTORY'])
    parser.add_argument('--expected-db-identifier', required=True)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--ssl-root-cert', required=True)
    args = parser.parse_args()
    try:
        import psycopg
        env = os.environ
        validate_environment(env)
        require(args.expected_db_identifier == DB_ID and args.expected_host == DB_HOST,
                'CLI target differs from the pinned P20 clone')
        require(os.path.isfile(args.ssl_root_cert), 'TLS trust anchor is unavailable')
        # Use an explicit transaction for role/grant creation. Never print SQL,
        # password, SCRAM verifier, environment, or exception text.
        with psycopg.connect(host=DB_HOST, port=5432, dbname=DB_NAME,
                             user=ADMIN_USER, password=env['DB_ADMIN_PASSWORD'],
                             sslmode='verify-full', sslrootcert=args.ssl_root_cert,
                             connect_timeout=10, autocommit=True,
                             options='-c statement_timeout=30000 -c lock_timeout=2000') as conn:
            with conn.transaction():
                result = provision_role(conn, ADMIN_USER, INVENTORY_USER, env['INVENTORY_DB_PASSWORD'])
        verified = verify_inventory_login(env, args.ssl_root_cert)
        print(json.dumps({'event': 'p20_c_inventory_credentials_verified',
                          'provisioned': result, 'verification': verified,
                          'secretsPrinted': False, 'databaseWrites': 'role and grants only',
                          'automaticRetry': False}))
        return 0
    except Exception as exc:
        # Exception text can include SQL fragments or parameters; emit only type.
        print(json.dumps({'event': 'p20_c_inventory_provisioning_stopped',
                          'exceptionType': type(exc).__name__, 'retryAllowed': False,
                          'secretsPrinted': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
