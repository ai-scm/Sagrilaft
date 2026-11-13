"""Ensayo optativo con el XML o ZIP real autorizado. No se ejecuta por defecto."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import UUID

import pytest
from sqlalchemy import select, text, func
from domain.listas.administracion import RecepcionPropuesta, PerfilOfacLocal
from infrastructure.listas.recepcion_archivo import ArchivoEnRecepcion, original_verificado
from infrastructure.persistencia.modelos_listas import (FuenteLista, VersionFuente, RegistroLista,
    IntentoImportacion, ArchivoFuente, FuenteVersionActiva, NombreRegistro, IdentificadorRegistro,
    DireccionRegistro, AtributoRegistro, RelacionRegistro)
from infrastructure.persistencia.modelos_importacion_listas import LoteImportacionLista, ControlImportacionVersion
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from services.listas.importacion_archivos import TrabajadorImportacionArchivos
from services.listas.comparacion_versiones import comparar_registros
from .test_flujo_http import portal
from .test_recepcion_f52 import carga


@pytest.mark.skipif(not os.environ.get('LISTAS_OFAC_ENSAYO_ARCHIVO'),reason='Requiere autorización explícita con --archivo-ofac')
def test_importacion_ofac_completa(carga,monkeypatch):
    inicio=time.monotonic()
    lote_esperado=PerfilOfacLocal().lote_registros
    origen=Path(os.environ['LISTAS_OFAC_ENSAYO_ARCHIVO'])
    resultados=Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO'])
    evidencia={'alcance':'SQL_LOCAL_DESECHABLE_OFAC_AUTORIZADO','estado':'EN_CURSO',
        'archivo':origen.name,'fecha_obtencion_copia_local':datetime.now(timezone.utc).isoformat(),
        'fecha_descarga_original':'NO_INFORMADA','errores':[]}
    def guardar(etapa):
        evidencia['etapa']=etapa;evidencia['segundos_totales']=round(time.monotonic()-inicio,3)
        (resultados/'ensayo-ofac-completo.json').write_text(json.dumps(evidencia,indent=2,ensure_ascii=False)+'\n')
    def huella(ruta):
        resumen=hashlib.sha256()
        with ruta.open('rb') as archivo:
            while bloque:=archivo.read(65536):resumen.update(bloque)
        return resumen.hexdigest()
    guardar('PREPARACION')
    huella_xml='60698e6e3edd49ac9398576aae7e98e06f2c0bf44cc41e485bca4732ac56805f'
    es_zip=origen.suffix.lower()=='.zip'
    formato='OFAC_ADVANCED_ZIP_V3' if es_zip else 'OFAC_ADVANCED_XML_V3'
    esperada='5b3a008cf8311f88f26c0b6da888a1271919fd30d5dc712f24073eb77791726c' if es_zip else huella_xml
    assert huella(origen)==esperada,'El ensayo exige revisar el archivo de 19.563 registros conocido'
    evidencia['formato']=formato
    monkeypatch.setenv('LISTAS_OFAC_LOCAL_HABILITADA','true')
    with carga.sesiones.begin() as sesion:
        sesion.add(FuenteLista(codigo='ofac_sdn',nombre='OFAC SDN ensayo de volumen',organismo='OFAC',
            url_oficial='https://sanctionslist.ofac.treas.gov/Home/SdnList'))
    datos=RecepcionPropuesta(fuente='ofac_sdn',formato=formato,nombre_original=origen.name,
        procedencia='https://sanctionslist.ofac.treas.gov/Home/SdnList',
        descargado_en=evidencia['fecha_obtencion_copia_local'],huella_declarada=esperada,clave='volumen-ofac-001')
    evidencia['nota_fecha_recepcion']='La fecha declarada corresponde a la obtención local para este ensayo, no a una descarga de OFAC acreditada.'
    etapa=time.monotonic();recepcion=carga.servicio.reservar(datos)
    assert carga.servicio.reservar(datos)==recepcion
    concesion=carga.servicio.reclamar(recepcion);assert concesion is not None
    escritura=ArchivoEnRecepcion(carga.custodia,carga.servicio.perfil.recibido_bytes)
    try:
        with origen.open('rb') as archivo:
            while bloque:=archivo.read(65536):escritura.escribir(bloque)
        objeto=escritura.confirmar(esperada)
        intento_id=carga.servicio.confirmar(recepcion,concesion[0],objeto)
    finally:escritura.cerrar()
    evidencia['recepcion']={'id':str(recepcion),'intento_id':str(intento_id),'sha256':esperada,
        'bytes':origen.stat().st_size,'segundos':round(time.monotonic()-etapa,3)}
    guardar('VALIDACION')
    etapa=time.monotonic()
    assert TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'development',True).ejecutar_uno()
    with carga.sesiones() as sesion:
        informe=sesion.get(IntentoImportacion,intento_id).informe
        assert informe['resultado']=='VALIDO',informe
        assert informe['registros']==19563
        assert informe['contenido_sha256']==huella_xml
        evidencia['validacion']={'registros':informe['registros'],'publicada_en':informe['publicada_en'],
            'segundos':round(time.monotonic()-etapa,3),'esquema_sha256':informe['esquema_sha256'],
            'contenido_sha256':informe['contenido_sha256'],'inventario':informe['entradas']}
    guardar('IMPORTACION_ANTES_SIGKILL')
    entorno=dict(os.environ,LISTAS_OFAC_LOCAL_HABILITADA='true')
    procesos=[]
    def lanzar(nombre,interrumpir=False):
        opciones={'custodia':str(carga.custodia.directorio),'interrumpir':interrumpir,
            'senal':str(resultados/(nombre+'-senal.json')),'avance':str(resultados/(nombre+'-avance.jsonl')),
            'resultado':str(resultados/(nombre+'-resultado.json'))}
        ruta=resultados/(nombre+'-opciones.json');ruta.write_text(json.dumps(opciones))
        salida=(resultados/(nombre+'-proceso.txt')).open('w')
        proceso=subprocess.Popen([sys.executable,'-m','tests.persistencia_listas.proceso_importacion_ofac',str(ruta)],
            env=entorno,stdout=salida,stderr=subprocess.STDOUT)
        procesos.append((proceso,salida));return proceso,opciones
    def resumen_bd():
        with carga.sesiones() as sesion:
            version=sesion.scalar(select(VersionFuente))
            lotes=list(sesion.scalars(select(LoteImportacionLista).order_by(LoteImportacionLista.desde)))
            control=sesion.get(ControlImportacionVersion,version.id)
            return {'version_id':str(version.id),'estado':version.estado,
                'registros':sesion.scalar(select(func.count()).select_from(RegistroLista)),
                'ordinal_confirmado':control.ordinal_confirmado,'numero_control':control.numero_control,
                'concesion_hasta':control.concesion_hasta.isoformat() if control.concesion_hasta else None,
                'lotes':[{'id':str(l.id),'desde':l.desde,'hasta':l.hasta,'huella':l.huella} for l in lotes]}
    try:
        proceso,opciones=lanzar('interrumpido',True);senal=Path(opciones['senal'])
        limite=time.monotonic()+1800
        while not senal.exists():
            assert proceso.poll() is None,(resultados/'interrumpido-proceso.txt').read_text()[-2000:]
            assert time.monotonic()<limite,'No se alcanzó el punto de interrupción'
            time.sleep(1)
        antes=resumen_bd()
        assert antes['estado']=='EN_CONSTRUCCION' and antes['registros']==lote_esperado
        assert antes['ordinal_confirmado']==lote_esperado and len(antes['lotes'])==1
        proceso.kill();assert proceso.wait(timeout=20)==-signal.SIGKILL
        despues=resumen_bd();assert despues==antes
        evidencia['interrupcion']={'tipo':'SIGKILL antes de confirmar el segundo lote',
            'antes':antes,'despues':despues,'salida_proceso':proceso.returncode}
        guardar('ESPERA_CONCESION_REAL')
        # El plazo transcurre realmente; no se alteran fechas ni concesiones con SQL.
        with carga.sesiones() as sesion:
            vencimiento=sesion.get(ControlImportacionVersion,UUID(antes['version_id'])).concesion_hasta
        espera=time.monotonic()
        while datetime.now(timezone.utc)<=vencimiento:
            time.sleep(min(1,max(.01,(vencimiento-datetime.now(timezone.utc)).total_seconds())))
        evidencia['interrupcion']['espera_segundos']=round(time.monotonic()-espera,3)
        guardar('REANUDACION')
        reanudado,opciones_reanudado=lanzar('reanudado')
        assert reanudado.wait(timeout=2400)==0,(resultados/'reanudado-proceso.txt').read_text()[-3000:]
        evidencia['trabajador_reanudado']=json.loads(Path(opciones_reanudado['resultado']).read_text())
        final=resumen_bd()
        assert final['version_id']==antes['version_id'] and final['estado']=='VALIDA'
        assert final['registros']==19563 and final['ordinal_confirmado']==19563
        assert final['lotes'][0]==antes['lotes'][0] and len(final['lotes'])==(19563+lote_esperado-1)//lote_esperado
        assert final['numero_control']>antes['numero_control']
        evidencia['recuperacion']=final
        guardar('COMPROBACION_FINAL')
        with carga.sesiones() as sesion:
            version=sesion.get(VersionFuente,UUID(final['version_id']))
            assert sesion.get(IntentoImportacion,intento_id).estado=='COMPLETADO'
            assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None
            conteos={t.__tablename__:sesion.scalar(select(func.count()).select_from(t)) for t in
                [RegistroLista,NombreRegistro,IdentificadorRegistro,DireccionRegistro,AtributoRegistro,RelacionRegistro]}
            assert conteos=={'registro_lista':19563,'nombre_registro':50238,'identificador_registro':23108,
                'direccion_registro':29725,'atributo_registro':1023351,'relacion_registro':9266}
            assert sesion.scalar(select(func.count(func.distinct(RegistroLista.uid_original))))==19563
            assert sesion.scalar(select(func.count()).select_from(RelacionRegistro).where(RelacionRegistro.registro_destino_id.is_(None)))==0
            assert version.manifiesto['registros']==19563 and version.publicada_en=='2026-11-06'
            raiz=sesion.get(ArchivoFuente,version.archivo_raiz_id)
            contenido=sesion.get(ArchivoFuente,version.archivo_contenido_id)
            assert raiz.huella==esperada and contenido.huella==huella_xml
            assert version.huella_contenido==huella_xml
            assert (raiz.id!=contenido.id)==es_zip
            evidencia['original_y_contenido']={'original_sha256':raiz.huella,
                'original_bytes':raiz.tamano_bytes,'contenido_sha256':contenido.huella,
                'contenido_bytes':contenido.tamano_bytes,'archivos_distintos':raiz.id!=contenido.id}
            for archivo in sesion.scalars(select(ArchivoFuente)):
                with original_verificado(carga.custodia,archivo.huella,archivo.tamano_bytes):pass
            comparacion=comparar_registros(sesion,None,version)
            assert comparacion['conteos']['ALTA']==19563
            evidencia['comparacion']={'conteos':comparacion['conteos'],'sha256':hashlib.sha256(json.dumps(comparacion,sort_keys=True).encode()).hexdigest()}
            evidencia['conteos']=conteos;evidencia['manifiesto']=version.manifiesto
            evidencia['almacenamiento']={'base_datos_bytes':sesion.scalar(text('SELECT pg_database_size(current_database())')),
                'tablas':[dict(r._mapping) for r in sesion.execute(text("""SELECT relname AS tabla,
                    pg_total_relation_size(relid) AS bytes_con_indices FROM pg_stat_user_tables
                    WHERE schemaname='public' AND relname IN
                    ('registro_lista','nombre_registro','identificador_registro','direccion_registro','atributo_registro','relacion_registro')
                    ORDER BY relname"""))],
                'custodia_bytes':sum(p.stat().st_size for p in carga.custodia.directorio.iterdir() if p.is_file())}
        assert carga.servicio.reclamar(recepcion) is None
        assert TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development',True).ejecutar_uno() is False
        assert huella(origen)==esperada
        evidencia['sin_duplicados']=True;evidencia['original_intacto']=True;evidencia['estado']='APROBADO'
        guardar('FINALIZADO')
    except BaseException as error:
        evidencia['estado']='FALLIDO';evidencia['errores'].append({'tipo':type(error).__name__,'mensaje':str(error)[-4000:]})
        guardar('FALLO');raise
    finally:
        for proceso,salida in procesos:
            if proceso.poll() is None:proceso.kill();proceso.wait(timeout=20)
            salida.close()
