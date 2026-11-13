#!/usr/bin/env python3
"""Trabajador F3 restringido al clúster desechable del arnés local."""
import argparse
import os
from pathlib import Path
import sys
import time

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))


def principal():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--una-vez", action="store_true")
    opciones = argumentos.parse_args()
    from sqlalchemy.engine import make_url
    ruta = Path(os.environ["LISTAS_PRUEBA_DIRECTORIO"]).resolve()
    url = make_url(os.environ["DATABASE_URL"])
    if (ruta.parent != Path("/tmp") or not ruta.name.startswith("listas-f2-")
            or url.host is not None or url.query.get("host") != str(ruta / "conexiones")
            or os.environ.get("APP_ENV") not in {"development", "test"}):
        raise RuntimeError("Solo se permite el clúster local desechable de pruebas")
    from infrastructure.config.configuracion import load_config
    from infrastructure.persistencia.database import SessionLocal
    from infrastructure.listas.custodia import CustodiaLocalListas
    from services.listas.politica_v2 import PoliticaListasV2
    from services.listas.trabajador import TrabajadorListas
    configuracion = load_config()
    trabajador = TrabajadorListas(SessionLocal, PoliticaListasV2(configuracion.listas_cautela, configuracion.entorno),
                                 CustodiaLocalListas(Path(os.environ["LISTAS_CUSTODIA_DIRECTORIO"])))
    while True:
        hubo_trabajo = trabajador.ejecutar_uno()
        if opciones.una_vez:
            return
        if not hubo_trabajo:
            time.sleep(1)


if __name__ == "__main__":
    principal()
