"""Proceso de ensayo que se detiene en un punto observable para recibir SIGKILL."""
import json
import os
from pathlib import Path
import signal
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from infrastructure.listas.custodia import CustodiaLocalListas
from services.listas.importacion_archivos import TrabajadorImportacionArchivos


def principal():
    opciones=json.loads(Path(sys.argv[1]).read_text())
    direccion=os.environ['LISTAS_PRUEBA_URL']; url=make_url(direccion)
    raiz=Path(os.environ['LISTAS_PRUEBA_DIRECTORIO']).resolve()
    assert raiz.parent==Path('/tmp') and raiz.name.startswith('listas-f2-')
    assert url.host is None and url.query.get('host')==str(raiz/'conexiones')
    motor=create_engine(direccion)
    @event.listens_for(motor,'connect')
    def restringir(conexion,_):
        with conexion.cursor() as cursor: cursor.execute('SET ROLE aplicacion_listas')
        conexion.commit()
    def observar(etapa,trabajo):
        if etapa==opciones.get('detener'):
            Path(opciones['senal']).write_text(json.dumps({'pid':os.getpid(),'etapa':etapa,'version_id':str(trabajo['version_id'])}))
            signal.pause()
    trabajador=TrabajadorImportacionArchivos(sessionmaker(motor,expire_on_commit=False),
        CustodiaLocalListas(Path(opciones['custodia'])),'development',habilitado=True,observador=observar)
    trabajador.perfil=trabajador.perfil.model_copy(update={'lote_registros':1,'concesion_segundos':3,'latido_segundos':1})
    try:
        trabajador.ejecutar_uno()
    finally:
        motor.dispose()


if __name__=='__main__': principal()
