#!/usr/bin/env python3
"""Comprueba un archivo OFAC local con el adaptador común; no usa base de datos."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import tempfile
import time

RAIZ=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(RAIZ/'backend'))


def principal():
    opciones=argparse.ArgumentParser(description=__doc__)
    opciones.add_argument('archivo',type=Path)
    opciones.add_argument('--formato',choices=['OFAC_ADVANCED_XML_V3','OFAC_ADVANCED_ZIP_V3'],required=True)
    opciones.add_argument('--resultado',type=Path,required=True)
    argumentos=opciones.parse_args()
    if argumentos.resultado.resolve()==argumentos.archivo.resolve():
        opciones.error('El resultado no puede sobrescribir el original')
    from infrastructure.listas.adaptadores_archivos import obtener_adaptador
    from infrastructure.listas.validacion_archivo import validar
    from infrastructure.listas.contenido_comparacion import contenido_canonico
    adaptador=obtener_adaptador(argumentos.formato);perfil=adaptador.perfil
    resource.setrlimit(resource.RLIMIT_AS,(perfil.memoria_bytes,perfil.memoria_bytes))
    resource.setrlimit(resource.RLIMIT_CPU,(perfil.validacion_segundos,perfil.validacion_segundos+1))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    inicio=time.monotonic();huella=hashlib.sha256()
    with argumentos.archivo.open('rb') as archivo:
        while bloque:=archivo.read(65536):huella.update(bloque)
    with tempfile.TemporaryDirectory(prefix='revision-ofac-') as temporal:
        informe=validar(argumentos.archivo,Path(temporal),argumentos.formato,perfil.model_dump())
        conteos=Counter()
        if informe['resultado']=='VALIDO':
            ruta=argumentos.archivo if argumentos.formato==adaptador.formato else Path(temporal)/'contenido.xml'
            with ruta.open('rb') as archivo:
                for registro in adaptador.registros(archivo):
                    conteos['registros']+=1
                    conteos['comparacion_resumida_bytes']+=len(json.dumps(contenido_canonico(registro, adaptador.comparacion_por_referencia),ensure_ascii=False).encode())
                    for campo,valores in adaptador.proyeccion(registro).items():conteos[campo]+=len(valores)
            if conteos['registros']!=informe['registros']:
                raise RuntimeError('Conteo de proyección distinto de la validación')
        resultado={'alcance':'VALIDACION_Y_PROYECCION_LOCAL_SIN_SQL',
            'archivo':argumentos.archivo.name,'original_sha256':huella.hexdigest(),
            'original_bytes':argumentos.archivo.stat().st_size,'validacion':informe,
            'proyeccion':dict(conteos),'segundos':round(time.monotonic()-inicio,3),
            'rss_maximo_kib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        with argumentos.resultado.open('x') as salida:json.dump(resultado,salida,indent=2,ensure_ascii=False)
        print(json.dumps({'resultado':informe['resultado'],'registros':conteos['registros'],'segundos':resultado['segundos']}))
        return 0 if informe['resultado']=='VALIDO' else 1


if __name__=='__main__':
    raise SystemExit(principal())
