#!/usr/bin/env python3
"""Ejecuta una importación F5.4 sobre el clúster local desechable, sin activar listas."""
import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'backend'))


def principal():
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from infrastructure.listas.custodia import CustodiaLocalListas
    from services.listas.importacion_archivos import TrabajadorImportacionArchivos
    direccion = os.environ['LISTAS_PRUEBA_URL']
    raiz = Path(os.environ['LISTAS_PRUEBA_DIRECTORIO']).resolve()
    url = make_url(direccion)
    if (raiz.parent != Path('/tmp') or not raiz.name.startswith('listas-f2-') or url.host is not None
            or url.query.get('host') != str(raiz / 'conexiones') or os.environ.get('APP_ENV') not in {'test', 'development'}):
        raise RuntimeError('Solo se admite la base desechable del arnés local')
    motor = create_engine(direccion)
    @event.listens_for(motor, 'connect')
    def restringir(conexion, _):
        with conexion.cursor() as cursor: cursor.execute('SET ROLE aplicacion_listas')
        conexion.commit()
    try:
        trabajador = TrabajadorImportacionArchivos(sessionmaker(motor, expire_on_commit=False),
            CustodiaLocalListas(Path(os.environ['LISTAS_CUSTODIA_DIRECTORIO'])), os.environ['APP_ENV'],
            habilitado=os.environ.get('LISTAS_ADMIN_HABILITADA') == 'true')
        print('Importación procesada' if trabajador.ejecutar_uno() else 'Sin importaciones disponibles')
    finally:
        motor.dispose()


if __name__ == '__main__':
    principal()
