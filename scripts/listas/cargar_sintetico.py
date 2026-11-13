#!/usr/bin/env python3
"""Carga manual local: conserva la misma clave al reintentar una transferencia."""
import argparse
import getpass
import hashlib
import http.client
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def principal():
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument('archivo', type=Path)
    opciones.add_argument('--url', default='http://127.0.0.1:8000')
    opciones.add_argument('--clave', required=True)
    opciones.add_argument('--formato', choices=['SINTETICO_XML_V1','SINTETICO_ZIP_V1','OFAC_ADVANCED_XML_V3','OFAC_ADVANCED_ZIP_V3'], required=True)
    opciones.add_argument('--descargado-en', help='Fecha real de descarga ISO 8601 con zona horaria; obligatoria para OFAC')
    opciones.add_argument('--token-archivo', type=Path, help='Archivo con el JWT (se lee, no se guarda); evita pegarlo en la terminal')
    argumentos = opciones.parse_args()
    es_ofac = argumentos.formato.startswith('OFAC_')
    if es_ofac and not argumentos.descargado_en:
        opciones.error('OFAC requiere --descargado-en con la fecha de descarga declarada')
    url = urlparse(argumentos.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        opciones.error('Solo se permite HTTP en 127.0.0.1, sin rutas ni credenciales')
    if argumentos.token_archivo:
        token = argumentos.token_archivo.read_text(encoding='utf-8', errors='ignore')
    else:
        token = getpass.getpass('JWT local (no se guarda): ')
    # Quita marcadores de pegado y caracteres de control que algunas terminales añaden.
    token = re.sub(r'\x1b\[[0-9;?]*[~a-zA-Z]|\[20[01]~', '', token)
    token = ''.join(c for c in token if c.isprintable()).strip()
    if token.lower().startswith('bearer '):
        token = token[7:].strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token):
        opciones.error('El JWT no tiene formato válido (3 partes separadas por puntos); puede estar vacío o truncado.')
    conexion = http.client.HTTPConnection('127.0.0.1', url.port or 80, timeout=300)
    try:
        with argumentos.archivo.open('rb') as archivo:
            huella = hashlib.sha256()
            tamano = 0
            while bloque := archivo.read(65536):
                tamano += len(bloque)
                if tamano > (268435456 if es_ofac else 104857600):
                    opciones.error('Archivo supera el límite del perfil local')
                huella.update(bloque)
            if not tamano:
                opciones.error('Archivo vacío')
            datos = dict(fuente='ofac_sdn' if es_ofac else 'ofac_sdn_prueba', formato=argumentos.formato,
                nombre_original=argumentos.archivo.name, procedencia='https://sanctionslist.ofac.treas.gov/Home/SdnList' if es_ofac else 'FIXTURE_LOCAL', huella_declarada=huella.hexdigest())
            if es_ofac:
                datos['descargado_en'] = argumentos.descargado_en
            conexion.request('POST', '/api/administracion-listas/recepciones', json.dumps(datos),
                {'Authorization':f'Bearer {token}','Content-Type':'application/json','Idempotency-Key':argumentos.clave})
            respuesta=conexion.getresponse(); contenido=respuesta.read()
            if respuesta.status != 201:
                raise RuntimeError(f'Reserva rechazada: HTTP {respuesta.status}')
            reserva=json.loads(contenido)
            recepcion=reserva['recepcion_id']
            print('Recepción:', recepcion)
            if reserva['estado'] == 'RECIBIDA':
                print('Original ya recibido; no se repite la transferencia')
                return
            archivo.seek(0)
            conexion.putrequest('PUT',f'/api/administracion-listas/recepciones/{recepcion}/contenido')
            conexion.putheader('Authorization',f'Bearer {token}')
            conexion.putheader('Content-Type','application/octet-stream')
            conexion.putheader('Content-Length',str(tamano))
            conexion.endheaders()
            while bloque := archivo.read(65536):
                conexion.send(bloque)
            respuesta=conexion.getresponse(); contenido=respuesta.read()
            if respuesta.status != 202:
                raise RuntimeError(f'Carga no confirmada: HTTP {respuesta.status}; reintente con la misma clave')
            print(contenido.decode())
    finally:
        conexion.close()


if __name__ == '__main__':
    principal()
