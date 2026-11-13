"""Proceso local que se pausa dentro de una generación no confirmada."""
import json
import os
from pathlib import Path
import signal
import sys
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from domain.listas.catalogos_busqueda import CatalogoPreparacion, IDENTIFICADORES_INICIALES
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.politica_v2 import ActorListas, PoliticaListasV2


def principal():
    opciones = json.loads(Path(sys.argv[1]).read_text())
    direccion = os.environ["LISTAS_PRUEBA_URL"]
    url = make_url(direccion)
    raiz = Path(os.environ["LISTAS_PRUEBA_DIRECTORIO"]).resolve()
    assert raiz.parent == Path("/tmp") and raiz.name.startswith("listas-f2-")
    assert url.host is None and url.query.get("host") == str(raiz / "conexiones")
    motor = create_engine(direccion)
    @event.listens_for(motor, "connect")
    def restringir(conexion, _):
        with conexion.cursor() as cursor:
            cursor.execute("SET ROLE aplicacion_listas")
        conexion.commit()
    def observar(etapa, _):
        if etapa == "registro_preparado":
            Path(opciones["senal"]).write_text("Generación sin confirmar")
            signal.pause()
    repositorio = RepositorioBusquedaListas(sessionmaker(motor, expire_on_commit=False),
        CustodiaLocalListas(Path(opciones["custodia"])),
        PoliticaListasV2(SagrilaftListasConfig(proveedor=None, implementacion="simulado",
            escenario="sin_coincidencias_v1", admin_habilitada=True), "development"),
        CatalogoPreparacion(version="ensayo-v1", identificadores=IDENTIFICADORES_INICIALES))
    actor = ActorListas.desde_identidad_validada("emisor-local", "operador-local", ("listas_cargador",))
    try:
        repositorio.preparar(actor, UUID(opciones["version"]), observar)
    finally:
        motor.dispose()


if __name__ == "__main__":
    principal()
