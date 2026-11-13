#!/usr/bin/env python3
"""Prueba F2 en un clúster PostgreSQL nuevo, temporal y sin puertos TCP."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[2]


def principal():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--binarios-postgres", type=Path, required=True)
    argumentos.add_argument("--directorio-resultados", type=Path, required=True)
    argumentos.add_argument("--seleccion", help="Filtro de pruebas pytest; no cambia la base desechable")
    argumentos.add_argument("--archivo-ofac", type=Path, help="Autoriza el ensayo seleccionado con este XML o ZIP local; no se descarga nada")
    opciones = argumentos.parse_args()
    if opciones.archivo_ofac is not None and not opciones.archivo_ofac.is_file():
        argumentos.error("El archivo OFAC debe existir localmente")
    binarios = opciones.binarios_postgres.resolve()
    resultados = opciones.directorio_resultados.resolve()
    resultados.mkdir(parents=True, mode=0o700, exist_ok=False)
    version = subprocess.check_output([str(binarios / "postgres"), "--version"], text=True)
    (resultados / "version.txt").write_text(version)
    # Entorno explícito: no heredar credenciales, URLs ni servicios PostgreSQL existentes.
    entorno = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8",
               "PYTHONPATH": str(RAIZ / "backend"), "AWS_EC2_METADATA_DISABLED": "true",
               "APP_ENV": "development", "SECRET_KEY": "solo-pruebas-aisladas",
               "PORTAL_INTERNO_URL": "https://portal.test", "PROVEEDOR_LISTAS_CAUTELA": "deshabilitado"}
    if opciones.archivo_ofac is not None:
        entorno["LISTAS_OFAC_ENSAYO_ARCHIVO"] = str(opciones.archivo_ofac.resolve())
    with tempfile.TemporaryDirectory(prefix="listas-f2-", dir="/tmp") as temporal:
        raiz = Path(temporal)
        datos, conexiones = raiz / "datos", raiz / "conexiones"
        conexiones.mkdir(mode=0o700)
        subprocess.run([str(binarios / "initdb"), "-D", str(datos), "-U", "pruebas_listas", "-A", "trust",
                        "--encoding=UTF8", "--locale=C"], env=entorno, check=True, stdout=subprocess.DEVNULL)
        with (datos / "postgresql.conf").open("a") as archivo:
            archivo.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{conexiones}'\nport = 55439\n")
        try:
            subprocess.run([str(binarios / "pg_ctl"), "-D", str(datos), "-l", str(resultados / "postgres.log"),
                            "-w", "start"], env=entorno, check=True, stdout=subprocess.DEVNULL)
            direccion = f"postgresql+psycopg://pruebas_listas@/postgres?host={conexiones}&port=55439"
            entorno.update(LISTAS_EVIDENCIAS_DIRECTORIO=str(resultados), DATABASE_URL=direccion, LISTAS_PRUEBA_URL=direccion, TEST_POSTGRES_ADMIN_URL=direccion,
                           LISTAS_PRUEBA_DIRECTORIO=temporal)
            proceso = subprocess.run([sys.executable, "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider",
                                      "--basetemp=" + str(raiz / "pruebas"),
                                      "tests/persistencia_listas", "tests/integration/test_migraciones_alembic_postgres.py", *(["-k", opciones.seleccion] if opciones.seleccion else []), f"--junitxml={resultados / 'pruebas.xml'}"],
                                     cwd=RAIZ, env=entorno, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (resultados / "pruebas.txt").write_text(proceso.stdout)
            print(proceso.stdout)
            return proceso.returncode
        finally:
            if (datos / "postmaster.pid").exists():
                subprocess.run([str(binarios / "pg_ctl"), "-D", str(datos), "-m", "fast", "-w", "stop"],
                               env=entorno, check=True, stdout=subprocess.DEVNULL)
            (resultados / "limpieza.txt").write_text("Clúster temporal detenido; datos eliminados al salir. No se utilizaron bases existentes.\n")


if __name__ == "__main__":
    raise SystemExit(principal())
