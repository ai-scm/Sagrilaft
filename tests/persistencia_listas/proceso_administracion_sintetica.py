"""Proceso aislado F5.5 para ensayos de SIGKILL; no conecta bases existentes."""
import json
import os
from pathlib import Path
import signal
import sys
from uuid import UUID
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from infrastructure.persistencia import models  # registra toda la metadata
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.config.configuracion import SagrilaftListasConfig
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.administracion_versiones import ServicioAdministracionVersiones
from services.listas.trabajador_comparacion import TrabajadorComparacionListas
from domain.listas.administracion import EjecucionAdministrativa


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
    def observar(etapa,operacion):
        if etapa==opciones.get('detener'):
            Path(opciones['senal']).write_text(json.dumps({'pid':os.getpid(),'etapa':etapa,'operacion':operacion}))
            signal.pause()
    sesiones=sessionmaker(motor,expire_on_commit=False)
    custodia=CustodiaLocalListas(Path(opciones['custodia']))
    try:
        if opciones['operacion']=='comparar':
            TrabajadorComparacionListas(sesiones,custodia,'development',True,observador=observar).ejecutar_uno()
        else:
            politica=PoliticaListasV2(SagrilaftListasConfig(proveedor=None,implementacion='simulado',escenario='sin_coincidencias_v1',admin_habilitada=True),'development')
            actor=ActorListas.desde_identidad_validada(opciones['emisor'],'revisor',('listas_aprobador',))
            servicio=ServicioAdministracionVersiones(sesiones,custodia,politica,actor,'development',
                lambda:UUID(opciones['politica']),observador=observar)
            servicio.ejecutar(EjecucionAdministrativa.model_validate(opciones['datos']))
    finally:
        motor.dispose()


if __name__=='__main__': principal()
