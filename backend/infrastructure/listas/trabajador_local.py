"""Procesa trabajos admitidos en la base del Docker Compose local."""
import logging
import os
from pathlib import Path
import signal
from threading import Event

from sqlalchemy.engine import make_url


def validar_destino():
    entorno = os.environ.get("APP_ENV")
    destino = make_url(os.environ["DATABASE_URL"])
    base = os.environ.get("LISTAS_BASE_LOCAL")
    if entorno != "development" or destino.host != "postgres" or not base or destino.database != base:
        raise RuntimeError("El trabajador requiere la base PostgreSQL del Compose local")
    return entorno


def principal():
    entorno = validar_destino()
    # Registra las relaciones con expedientes antes de crear sesiones.
    from infrastructure.persistencia import models
    from infrastructure.persistencia.database import SessionLocal
    from infrastructure.config.configuracion import SagrilaftListasConfig
    from infrastructure.listas.custodia import CustodiaLocalListas
    from services.listas.politica_v2 import PoliticaListasV2
    from services.listas.trabajador import TrabajadorListas
    from services.listas.validacion_archivos import TrabajadorValidacionArchivos
    from services.listas.importacion_archivos import TrabajadorImportacionArchivos
    from services.listas.trabajador_comparacion import TrabajadorComparacionListas
    from services.listas.trabajador_preparacion_busqueda import TrabajadorPreparacionBusqueda

    configuracion = SagrilaftListasConfig()
    custodia = CustodiaLocalListas(Path(os.environ["LISTAS_CUSTODIA_DIRECTORIO"]))
    trabajadores = [TrabajadorListas(SessionLocal, PoliticaListasV2(configuracion, entorno), custodia)]
    if configuracion.admin_habilitada:
        trabajadores.extend([
            TrabajadorValidacionArchivos(SessionLocal, custodia, entorno, True),
            TrabajadorImportacionArchivos(SessionLocal, custodia, entorno, True),
            TrabajadorComparacionListas(SessionLocal, custodia, entorno, True),
            # Solo versiones ya activadas por una persona; no aprueba ni activa.
            TrabajadorPreparacionBusqueda(SessionLocal, custodia, PoliticaListasV2(configuracion, entorno), entorno, True),
        ])
    detener = Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())
    logging.basicConfig(level=logging.INFO)
    logging.info("Trabajador local iniciado; no aprueba ni activa versiones; prepara la búsqueda de las ya activas")
    while not detener.is_set():
        hubo_trabajo = False
        for trabajador in trabajadores:
            if detener.is_set():
                break
            hubo_trabajo = trabajador.ejecutar_uno() or hubo_trabajo
        if not hubo_trabajo:
            detener.wait(2)


if __name__ == "__main__":
    principal()
