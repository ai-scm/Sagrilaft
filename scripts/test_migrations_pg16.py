#!/usr/bin/env python3
"""Run migration tests on a NEW PostgreSQL 16 cluster, Unix socket only.

No Docker, AWS, existing database or application .env is used.
Requires locally installed initdb/pg_ctl/postgres binaries; does not install them.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True, help='New directory for evidence')
    args = parser.parse_args()
    binaries = args.pg_bin.resolve()
    version = subprocess.check_output([str(binaries / 'postgres'), '--version'], text=True).strip()
    if not version.startswith('postgres (PostgreSQL) 16.'):
        parser.error(f'PostgreSQL 16 required; found {version}')
    reports = args.report_dir.resolve()
    reports.mkdir(mode=0o700, parents=True, exist_ok=False)
    (reports / 'version.txt').write_text(version + '\n')
    with tempfile.TemporaryDirectory(prefix='sagrilaft-pg16-', dir='/tmp') as directory:
        cluster = Path(directory)
        data, socket = cluster / 'data', cluster / 'socket'
        socket.mkdir(mode=0o700)
        # Do not inherit libpq options/service files/passwords or application config.
        env = {k: v for k, v in os.environ.items() if not k.startswith(('PG', 'TEST_POSTGRES', 'MIGRATION_'))}
        subprocess.run([str(binaries / 'initdb'), '-D', str(data), '-U', 'migration_test',
                        '-A', 'trust', '--encoding=UTF8', '--locale=C'], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        with (data / 'postgresql.conf').open('a') as config:
            config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{socket}'\nport = 55432\n")
        try:
            subprocess.run([str(binaries / 'pg_ctl'), '-D', str(data), '-l', str(reports / 'postgres.log'),
                            '-w', 'start'], env=env, check=True)
            env.update(TEST_POSTGRES_ADMIN_URL=f'postgresql+psycopg://migration_test@/postgres?host={socket}&port=55432',
                       TEST_POSTGRES_EXPECTED_MAJOR='16', APP_ENV='development',
                       DATABASE_URL=f'postgresql+psycopg://migration_test@/postgres?host={socket}&port=55432', SECRET_KEY='local-migration-test',
                       PORTAL_INTERNO_URL='https://portal.test')
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-ra', '-p', 'no:cacheprovider',
                'tests/integration/test_migraciones_alembic_postgres.py',
                'tests/unit/test_migration_guard.py', f'--junitxml={reports / "pytest.xml"}'],
                cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (reports / 'pytest.txt').write_text(result.stdout)
            print(result.stdout)
            import psycopg
            with psycopg.connect(host=str(socket), port=55432, dbname='postgres', user='migration_test') as connection:
                server_version = connection.execute('SHOW server_version').fetchone()[0]
                remaining = connection.execute(
                    "SELECT datname FROM pg_database WHERE datname LIKE 'sagrilaft_alembic_test_%'"
                ).fetchall()
                assert server_version.split('.')[0] == '16'
            (reports / 'database-check.json').write_text(json.dumps({
                'server_version': server_version, 'temporary_databases_remaining': remaining,
                'pytest_exit_code': result.returncode, 'listen_addresses': '', 'locale': 'C'
            }, indent=2) + '\n')
            if remaining:
                raise RuntimeError('Tests left temporary databases; see database-check.json')
            return result.returncode
        finally:
            if (data / 'postmaster.pid').exists():
                subprocess.run([str(binaries / 'pg_ctl'), '-D', str(data), '-m', 'fast', '-w', 'stop'],
                               env=env, check=True)
            (reports / 'cleanup.txt').write_text('Temporary cluster stopped; data removed on runner exit.\n')


if __name__ == '__main__':
    raise SystemExit(main())
