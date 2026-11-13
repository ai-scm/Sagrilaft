#!/usr/bin/env python3
"""Cliente F5.5: usa la API local y pide el JWT sin guardarlo ni mostrarlo."""
import argparse
import getpass
import http.client
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID


def peticion(operacion, identificador=None):
    rutas = {
        'comparar': ('POST', '/comparaciones'), 'solicitar': ('POST', '/solicitudes'),
        'informe': ('GET', '/comparaciones/{id}'), 'consultar': ('GET', '/solicitudes/{id}'),
        'decidir': ('POST', '/solicitudes/{id}/decisiones'),
        'ejecutar': ('POST', '/solicitudes/{id}/ejecuciones'),
        'revocar': ('POST', '/revisiones/{id}/revocaciones'),
        'bloquear': ('POST', '/versiones/{id}/bloqueos'),
    }
    metodo, ruta = rutas[operacion]
    if '{id}' in ruta:
        ruta = ruta.format(id=str(UUID(identificador)))
    return metodo, '/api/administracion-listas' + ruta


def principal():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operacion', choices=['comparar','solicitar','informe','consultar','decidir','ejecutar','revocar','bloquear'])
    parser.add_argument('--id')
    parser.add_argument('--datos', type=Path, help='JSON del contrato F5.1, incluida clave de idempotencia')
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--token-archivo', type=Path, help='Archivo con el JWT (se lee, no se guarda)')
    opciones = parser.parse_args()
    url = urlparse(opciones.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        parser.error('Solo se permite HTTP en 127.0.0.1, sin rutas ni credenciales')
    try:
        metodo, ruta = peticion(opciones.operacion, opciones.id)
    except (ValueError, TypeError):
        parser.error('Se requiere un UUID válido para esta operación')
    contenido = None
    if metodo == 'POST':
        if opciones.datos is None or opciones.datos.stat().st_size > 65536:
            parser.error('Se requiere un JSON de hasta 64 KiB')
        contenido = json.dumps(json.loads(opciones.datos.read_text()))
    if opciones.token_archivo:
        token = opciones.token_archivo.read_text(encoding='utf-8', errors='ignore')
    else:
        token = getpass.getpass('JWT local (no se guarda): ')
    import re
    token = ''.join(c for c in re.sub(r'\x1b\[[0-9;?]*[~a-zA-Z]|\[20[01]~', '', token) if c.isprintable()).strip()
    if token.lower().startswith('bearer '):
        token = token[7:].strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token):
        parser.error('El JWT no tiene formato válido (3 partes separadas por puntos).')
    conexion = http.client.HTTPConnection('127.0.0.1', url.port or 80, timeout=60)
    try:
        conexion.request(metodo, ruta, contenido, {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read()
        if not 200 <= respuesta.status < 300:
            raise SystemExit(f'Operación no confirmada: HTTP {respuesta.status}. Consulte el estado antes de reintentar con la misma clave.')
        print(cuerpo.decode())
    finally:
        conexion.close()


if __name__ == '__main__':
    principal()
