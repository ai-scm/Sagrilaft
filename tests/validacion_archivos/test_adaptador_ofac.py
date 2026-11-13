"""Casos relevantes del adaptador oficial, con sujetos ficticios y XSD revisado."""
from pathlib import Path
import hashlib
import zipfile
import pytest
from lxml import etree
from infrastructure.listas.adaptadores_archivos import obtener_adaptador
from infrastructure.listas.validacion_archivo import validar
from infrastructure.listas.adaptador_ofac import ESPACIO, ESQUEMA

FIJO = Path(__file__).resolve().parents[1] / 'fixtures/ofac_advanced/dos_entidades.xml'


def test_xsd_mapeo_nombres_documentos_relaciones_y_catalogos(tmp_path):
    adaptador = obtener_adaptador('OFAC_ADVANCED_XML_V3')
    informe = validar(FIJO, tmp_path, adaptador.formato, adaptador.perfil.model_dump())
    assert informe['resultado'] == 'VALIDO', informe
    assert informe['registros'] == 2 and informe['publicada_en'] == '2026-11-06'
    with FIJO.open('rb') as archivo:
        registros = list(adaptador.registros(archivo))
    primero = adaptador.proyeccion(registros[0])
    assert len(primero['nombres']) == 2
    assert primero['identificadores'][0]['original'] == '00001231'
    assert primero['identificadores'][0]['pais_emisor'] == 'MX'
    assert primero['relaciones'][0]['identificador_destino'] == '9002'
    assert registros[0]['sanciones'] and registros[0]['catalogos']
    assert registros[0]['sujeto']['atributos']['FixedRef'] == '9001'


def test_zip_conserva_hash_del_xml(tmp_path):
    ruta=tmp_path/'lista.zip'
    with zipfile.ZipFile(ruta,'w',zipfile.ZIP_DEFLATED) as salida:salida.write(FIJO,'SDN_ADVANCED.XML')
    adaptador=obtener_adaptador('OFAC_ADVANCED_ZIP_V3')
    informe=validar(ruta,tmp_path,'OFAC_ADVANCED_ZIP_V3',adaptador.perfil.model_dump())
    assert informe['resultado']=='VALIDO',informe
    assert informe['contenido_sha256']==hashlib.sha256(FIJO.read_bytes()).hexdigest()


@pytest.mark.parametrize('caso', ['referencia_rota','uid_duplicado','namespace','delta','no_sdn','dtd','fecha'])
def test_rechaza_archivo_incompatible(tmp_path,caso):
    raiz=etree.fromstring(FIJO.read_bytes());q=lambda n:'{'+ESPACIO+'}'+n
    if caso=='referencia_rota':raiz.find('.//'+q('ProfileRelationship')).set('To-ProfileID','999999999')
    elif caso=='uid_duplicado':
        sujetos=raiz.findall('.//'+q('DistinctParty'));sujetos[1].set('FixedRef',sujetos[0].get('FixedRef'))
    elif caso=='namespace':raiz.tag='{urn:otra-lista}Sanctions'
    elif caso=='delta':raiz.set('DeltaBaseVersion','2')
    elif caso=='no_sdn':
        for entrada in raiz.findall('.//'+q('SanctionsEntry')):entrada.set('ListID','91512')
    elif caso=='fecha':raiz.find('.//'+q('DateOfIssue')+'/'+q('Day')).text=None
    datos=etree.tostring(raiz)
    if caso=='dtd':datos=b'<!DOCTYPE Sanctions [<!ENTITY x SYSTEM "file:///etc/passwd">]>'+datos
    ruta=tmp_path/'invalido.xml';ruta.write_bytes(datos)
    a=obtener_adaptador('OFAC_ADVANCED_XML_V3')
    assert validar(ruta,tmp_path,a.formato,a.perfil.model_dump())['resultado']=='INVALIDO'


def test_esquema_fijado_y_limites_independientes(tmp_path,monkeypatch):
    from infrastructure.listas import adaptador_ofac
    falso=tmp_path/'schema.xsd';falso.write_bytes(ESQUEMA.read_bytes()+b' ')
    monkeypatch.setattr(adaptador_ofac,'ESQUEMA',falso)
    a=obtener_adaptador('OFAC_ADVANCED_XML_V3')
    assert validar(FIJO,tmp_path,a.formato,a.perfil.model_dump())['codigo']=='ESQUEMA_ALTERADO'
    assert a.perfil.recibido_bytes==268435456
    assert a.perfil.lote_registros==100
    assert a.perfil.codigo=='ofac-advanced-local-v2'
    assert obtener_adaptador('SINTETICO_XML_V1').perfil.lote_registros==1000
    assert obtener_adaptador('SINTETICO_XML_V1').perfil.recibido_bytes==104857600


def test_indice_temporal_se_libera_con_sigkill(tmp_path):
    """El índice desechable no debe dejar archivos abandonados tras morir el proceso."""
    import json,os,signal,subprocess,sys,time
    senal=tmp_path/'senal.json'
    programa='''
import json,os,signal,sys
from pathlib import Path
from infrastructure.listas.adaptador_ofac import indice
with Path(sys.argv[1]).open('rb') as archivo, indice(archivo) as (conexion,_):
    conexion.executemany('INSERT INTO objeto VALUES (?,?,?)',
        [('ensayo',str(i),'x'*3000) for i in range(2000)])
    conexion.commit()
    destinos=[]
    for entrada in Path('/proc/self/fd').iterdir():
        try:
            ruta=os.readlink(entrada)
            if 'etilqs' in ruta: destinos.append(ruta)
        except FileNotFoundError: pass
    Path(sys.argv[2]).write_text(json.dumps({'archivos':destinos,
        'nombre_sqlite':conexion.execute('PRAGMA database_list').fetchone()[2]}))
    signal.pause()
'''
    raiz_backend=str(Path(__file__).resolve().parents[2]/'backend')
    entorno=dict(os.environ,SQLITE_TMPDIR=str(tmp_path),TMPDIR=str(tmp_path),PYTHONPATH=raiz_backend)
    proceso=subprocess.Popen([sys.executable,'-c',programa,str(FIJO),str(senal)],env=entorno,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        limite=time.monotonic()+10
        while not senal.exists():
            assert proceso.poll() is None,proceso.communicate()[1].decode() if proceso.poll() is not None else ''
            assert time.monotonic()<limite
            time.sleep(.02)
        datos=json.loads(senal.read_text())
        assert datos['nombre_sqlite']==''
        assert datos['archivos'] and all(n.endswith(' (deleted)') for n in datos['archivos'])
        proceso.kill();assert proceso.wait(timeout=5)==-signal.SIGKILL
        assert sorted(p.name for p in tmp_path.iterdir())==['senal.json']
    finally:
        if proceso.poll() is None:proceso.kill();proceso.wait(timeout=5)
        proceso.communicate()
