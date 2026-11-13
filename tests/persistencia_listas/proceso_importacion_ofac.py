"""Trabajador real del ensayo optativo de volumen; puede pausarse antes del segundo commit."""
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from infrastructure.listas.custodia import CustodiaLocalListas
from services.listas.importacion_archivos import TrabajadorImportacionArchivos


def principal():
    opciones=json.loads(Path(sys.argv[1]).read_text())
    direccion=os.environ['LISTAS_PRUEBA_URL'];url=make_url(direccion)
    raiz=Path(os.environ['LISTAS_PRUEBA_DIRECTORIO']).resolve()
    assert raiz.parent==Path('/tmp') and raiz.name.startswith('listas-f2-')
    assert url.host is None and url.query.get('host')==str(raiz/'conexiones')
    assert os.environ.get('LISTAS_OFAC_LOCAL_HABILITADA')=='true'
    motor=create_engine(direccion)
    @event.listens_for(motor,'connect')
    def restringir(conexion,_):
        with conexion.cursor() as cursor:cursor.execute('SET ROLE aplicacion_listas')
        conexion.commit()
    lotes=0;inicio=time.monotonic()
    def observar(etapa,trabajo):
        nonlocal lotes
        if etapa=='antes_commit_lote':
            lotes+=1
            if opciones.get('interrumpir') and lotes==2:
                Path(opciones['senal']).write_text(json.dumps({'pid':os.getpid(),'etapa':etapa,
                    'version_id':str(trabajo['version_id']),'lotes_intentados':lotes}))
                signal.pause()
        if etapa in {'despues_commit_lote','antes_commit_sellado','despues_commit_sellado'}:
            with Path(opciones['avance']).open('a') as salida:
                salida.write(json.dumps({'etapa':etapa,'lotes_proceso':lotes,
                    'segundos':round(time.monotonic()-inicio,3)})+'\n')
    trabajador=TrabajadorImportacionArchivos(sessionmaker(motor,expire_on_commit=False),
        CustodiaLocalListas(Path(opciones['custodia'])),'development',habilitado=True,observador=observar)
    # Mismos límites de memoria y CPU que el perfil; no se acortan concesiones ni lotes.
    from domain.listas.administracion import PerfilOfacLocal
    perfil=PerfilOfacLocal()
    resource.setrlimit(resource.RLIMIT_AS,(perfil.memoria_bytes,perfil.memoria_bytes))
    resource.setrlimit(resource.RLIMIT_CPU,(perfil.intento_segundos,perfil.intento_segundos+1))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    try:
        procesado=trabajador.ejecutar_uno()
        Path(opciones['resultado']).write_text(json.dumps({'procesado':procesado,
            'segundos':round(time.monotonic()-inicio,3),
            'rss_maximo_kib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
    finally:
        motor.dispose()


if __name__=='__main__':principal()
