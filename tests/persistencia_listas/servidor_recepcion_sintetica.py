"""Proceso HTTP desechable para ensayar SIGKILL durante una carga F5.2."""
import json
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
import uvicorn

from api import dependencias_listas
from api.middleware import autenticacion
from api.routers import recepciones_listas
from domain.listas.administracion import PerfilEnsayo
from infrastructure.config.configuracion import KeycloakConfig, SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
import services.listas.recepcion as recepcion


def principal():
    configuracion = json.loads(Path(sys.argv[1]).read_text())
    direccion = os.environ['LISTAS_PRUEBA_URL']
    raiz = Path(os.environ['LISTAS_PRUEBA_DIRECTORIO']).resolve()
    url = make_url(direccion)
    assert raiz.parent == Path('/tmp') and raiz.name.startswith('listas-f2-')
    assert url.host is None and url.query.get('host') == str(raiz / 'conexiones')
    motor = create_engine(direccion)

    @event.listens_for(motor, 'connect')
    def restringir(conexion, _):
        with conexion.cursor() as cursor:
            cursor.execute('SET ROLE aplicacion_listas')
        conexion.commit()

    async def claves_locales(_):
        return {'keys': [configuracion['jwk']]}

    autenticacion._obtener_jwks = claves_locales
    autenticacion._AUTH_DESHABILITADA = False
    # Solo acorta la prueba. La concesión conserva los 30 segundos de margen reales.
    perfil = PerfilEnsayo().model_dump()
    perfil['carga_segundos'] = 2
    recepcion.PerfilEnsayo = lambda: SimpleNamespace(**perfil)
    aplicacion = FastAPI()
    aplicacion.state.config = SimpleNamespace(
        keycloak=KeycloakConfig(url='http://identidad.local', realm='pruebas', client_id='portal'),
        listas_cautela=SagrilaftListasConfig(proveedor=None, implementacion='simulado',
            escenario='sin_coincidencias_v1', admin_habilitada=True), entorno='development')
    sesiones = sessionmaker(motor, expire_on_commit=False)
    custodia = CustodiaLocalListas(Path(configuracion['custodia']))
    aplicacion.dependency_overrides[dependencias_listas.sesiones_listas] = lambda: sesiones
    aplicacion.dependency_overrides[dependencias_listas.custodia_listas] = lambda: custodia
    aplicacion.include_router(recepciones_listas.enrutador)
    with socket.socket() as conexion:
        conexion.bind(('127.0.0.1', 0))
        Path(configuracion['puerto']).write_text(str(conexion.getsockname()[1]))
        servidor = uvicorn.Server(uvicorn.Config(aplicacion, log_level='error'))
        servidor.run(sockets=[conexion])
    motor.dispose()


if __name__ == '__main__':
    principal()
