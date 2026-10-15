#!/usr/bin/env python3
"""P20 C fixture. Default is offline review; no project Alembic commands."""
import argparse
import json
import os
from pathlib import Path
import re

LAB = 'p20-9c67b6ea6842'
WORK = LAB + '-c7-test-20261012'
RESTORE = LAB + '-restore-c-20261014'
WORK_HOST = WORK + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
RESTORE_HOST = RESTORE + '.cbm5sq1kjl57.us-east-1.rds.amazonaws.com'
UID = '73bf8b16-9551-4656-965d-518afc19d7d1'
MARKER = 'P20-9c67b6ea6842-SMOKE-20261014T013047Z-0fd1ff'
CITY = 'P20 prueba de recuperación B'
DDL = 'ALTER TABLE public.formularios RENAME COLUMN razon_social TO p20_c_razon_social'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def validate_target(env, identifier, host, action, apply=False, receipt_hash=None):
    require(env.get('P20_RUN_ID') == LAB and env.get('ZOHO_SIGN_ENABLED') == 'false'
            and env.get('RUN_MODE') == 'p20-c-fixture', 'Wrong P20/Zoho/runtime')
    if action == 'verify-restored':
        require(identifier == RESTORE, 'Wrong instance for this C phase')
    elif action == 'inventory':
        require(identifier in (WORK, RESTORE), 'Inventory target is outside the approved P20 C databases')
    else:
        require(identifier == WORK, 'Wrong instance for this C phase')
    require(bool(re.fullmatch(re.escape(identifier) + r'\.[a-z0-9]+\.us-east-1\.rds\.amazonaws\.com', host)), 'Wrong endpoint')
    if identifier == WORK:
        require(host == WORK_HOST, 'Working endpoint differs')
    elif identifier == RESTORE:
        require(host == RESTORE_HOST, 'Restored endpoint differs')
    require(env.get('DATABASE_HOST') == host and env.get('DATABASE_NAME') == 'sagrilaft', 'Conflicting DB settings')
    require('DATABASE_URL' not in env, 'DATABASE_URL is forbidden; use the pinned host and database')
    if action == 'inventory':
        require(env.get('DB_USER') == 'p20_c_inventory', 'Inventory requires the dedicated read-only PostgreSQL role')
    if apply:
        require(action == 'incompatibility' and identifier == WORK, 'Only approved working clone DDL')
        require(bool(re.fullmatch(r'[a-f0-9]{64}', receipt_hash or ''))
                and env.get('P20_C_GUARD_SHA256') == receipt_hash, 'Missing validated backup/containment receipt')


def controls(conn, incompatible=False):
    from psycopg import sql
    require([r[0] for r in conn.execute('SELECT version_num FROM public.alembic_version')] == ['c7a1c1a65662'], 'Main revision differs')
    require([r[0] for r in conn.execute('SELECT version_num FROM public.p20_b_alembic_version')] == ['p20b_expand_01'], 'B marker differs')
    columns = {r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='formularios'")}
    original, renamed = 'razon_social' in columns, 'p20_c_razon_social' in columns
    require((not original and renamed) if incompatible else (original and not renamed), 'Unexpected C column state')
    shape = conn.execute("SELECT data_type,is_nullable,character_maximum_length,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='formularios' AND column_name='p20_b_probe'").fetchone()
    require(shape == ('character varying', 'YES', 64, None), 'B expansion differs')
    name = 'p20_c_razon_social' if incompatible else 'razon_social'
    rows = conn.execute(sql.SQL('SELECT id,{},ciudad,estado,p20_b_probe FROM public.formularios WHERE id=%s').format(sql.Identifier(name)), (UID,)).fetchall()
    require(len(rows) == 1 and tuple(str(v) for v in rows[0][:4]) == (UID, MARKER, CITY, 'borrador'), 'Synthetic baseline differs')
    # Keep row-count queries inside the exact SELECT grants given to the
    # inventory role. Catalog names remain visible without table-wide SELECT.
    count_columns = {'alembic_version': 'version_num',
                     'p20_b_alembic_version': 'version_num',
                     'formularios': 'id'}
    counts = {table: conn.execute(
        sql.SQL('SELECT count({}) FROM public.{}').format(sql.Identifier(column), sql.Identifier(table))
    ).fetchone()[0] for table, column in count_columns.items()}
    return {'mainRevision': 'c7a1c1a65662', 'bRevision': 'p20b_expand_01', 'formId': UID,
            'city': CITY, 'state': 'borrador', 'bProbe': rows[0][4], 'tableCounts': counts, 'incompatible': incompatible}


def apply_connection(conn):
    require(conn.info.transaction_status.name == 'INTRANS', 'Explicit transaction required')
    conn.execute("SET LOCAL lock_timeout='2s'")
    conn.execute("SET LOCAL statement_timeout='30s'")
    before = controls(conn)
    conn.execute(DDL)
    after = controls(conn, incompatible=True)
    require({k: v for k, v in before.items() if k != 'incompatible'} ==
            {k: v for k, v in after.items() if k != 'incompatible'}, 'Control changed beyond column rename')
    return after


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['inventory', 'incompatibility', 'verify-incompatible', 'verify-restored'])
    p.add_argument('--db-identifier', required=True)
    p.add_argument('--expected-host', required=True)
    p.add_argument('--ssl-root-cert')
    p.add_argument('--query', action='store_true', help='Read-only queries; requires separately authorized task')
    p.add_argument('--apply', action='store_true', help='One guarded DDL transaction; separately approved')
    p.add_argument('--guard-receipt-sha256')
    a = p.parse_args()
    try:
        validate_target(os.environ, a.db_identifier, a.expected_host, a.action, a.apply, a.guard_receipt_sha256)
        require(not (a.query and a.apply), 'Choose read-only or DDL')
        if not a.query and not a.apply:
            print(json.dumps({'status': 'OFFLINE_REVIEW_ONLY', 'action': a.action, 'ddl': DDL,
                              'databaseTouched': False, 'applyRequiresReceiptAndApproval': True}))
            return 0
        require(a.ssl_root_cert and Path(a.ssl_root_cert).is_file(), 'TLS trust anchor required')
        require(a.apply == (a.action == 'incompatibility'), 'DDL is only available in incompatibility phase')
        if a.action == 'inventory':
            require(a.query and not a.apply and os.environ.get('DB_USER') == 'p20_c_inventory',
                    'Inventory is query-only and requires its dedicated PostgreSQL role')
        import psycopg
        with psycopg.connect(host=a.expected_host, port=5432, dbname='sagrilaft',
                              user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                              sslmode='verify-full', sslrootcert=a.ssl_root_cert, connect_timeout=10,
                              autocommit=True, options='-c statement_timeout=30000 -c lock_timeout=2000' +
                              ('' if a.apply else ' -c default_transaction_read_only=on')) as conn:
            require(conn.execute('SELECT current_database()').fetchone()[0] == 'sagrilaft'
                    and conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0] is True, 'Wrong DB/TLS')
            if a.action == 'inventory':
                require(conn.execute('SELECT current_user').fetchone()[0] == 'p20_c_inventory',
                        'Connected PostgreSQL role differs from the read-only inventory role')
            if a.apply:
                with conn.transaction():
                    result = apply_connection(conn)
            else:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result = controls(conn, incompatible=a.action == 'verify-incompatible')
                    if a.action == 'verify-incompatible':
                        try:
                            with conn.transaction():
                                conn.execute('SELECT razon_social FROM public.formularios WHERE id=%s', (UID,))
                        except psycopg.errors.UndefinedColumn as exc:
                            require(exc.sqlstate == '42703', 'Wrong SQL error')
                            result['expectedSqlstate'] = exc.sqlstate
                        else:
                            raise RuntimeError('Old column unexpectedly works')
        print(json.dumps({'event': 'p20_c_fixture_verified', 'action': a.action,
                          'ddlCommitted': a.apply, 'controls': result, 'automaticRetry': False}))
        return 0
    except Exception as exc:
        print(json.dumps({'event': 'p20_c_fixture_stopped', 'exceptionType': type(exc).__name__, 'retryAllowed': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
