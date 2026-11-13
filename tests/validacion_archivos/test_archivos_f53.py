"""Solo datos sintéticos; pruebas negativas y fronteras del perfil F5.3."""
import hashlib
import io
from pathlib import Path
import struct
import zipfile
import pytest
from domain.listas.administracion import PerfilEnsayo
from infrastructure.listas.validacion_archivo import validar, comprobar_xml, RechazoArchivo

FIJOS = Path(__file__).resolve().parents[1] / 'fixtures/listas_f5'
XML = (FIJOS / 'v1.xml').read_bytes()


def ejecutar(tmp_path, contenido=XML, formato='SINTETICO_XML_V1', **limites):
    original = tmp_path / 'original.bin'; original.write_bytes(contenido)
    perfil = PerfilEnsayo().model_dump(); perfil.update(limites)
    return validar(original, tmp_path, formato, perfil)


def comprimir(entradas, compresion=zipfile.ZIP_STORED):
    salida=io.BytesIO()
    with zipfile.ZipFile(salida, 'w', compression=compresion) as archivo:
        for nombre, contenido in entradas: archivo.writestr(nombre, contenido)
    return salida.getvalue()


@pytest.mark.parametrize('archivo,formato',[('v1.xml','SINTETICO_XML_V1'),('v2.xml','SINTETICO_XML_V1'),('v1.zip','SINTETICO_ZIP_V1')])
def test_fixtures_validos(tmp_path,archivo,formato):
    resultado=ejecutar(tmp_path,(FIJOS/archivo).read_bytes(),formato)
    assert resultado['resultado']=='VALIDO' and resultado['registros']==2


@pytest.mark.parametrize('contenido,codigo',[
    (XML[:-20],'XML_MAL_FORMADO'),
    (XML.replace(b'urn:sagrilaft:pruebas:listas:v1',b'urn:otro'),'PRODUCTO_NO_SOPORTADO'),
    (XML.replace(b'sintetica="true"',b'sintetica="false"'),'PRODUCTO_NO_SOPORTADO'),
    (XML.replace(b'destino="prueba_empresa"',b'destino="ausente"'),'REFERENCIA_ROTA'),
    (XML.replace(b'<nombre>Empresa ficticia Uno</nombre>',b'<nombre> </nombre>'),'NOMBRE_VACIO'),
    (XML.replace(b'uid="prueba_empresa"',b'uid="prueba_persona"'),'XSD_INVALIDO'),
    (XML.replace(b'</lista>',b'<desconocido/></lista>'),'XSD_INVALIDO'),
    (b'<!DOCTYPE lista [<!ENTITY x "dato">]><lista/>','DTD_PROHIBIDO'),
    (b'<lista xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="file:///etc/passwd"/></lista>','XINCLUDE_PROHIBIDO'),
])
def test_xml_rechazado(tmp_path,contenido,codigo):
    assert ejecutar(tmp_path,contenido)['codigo']==codigo


@pytest.mark.parametrize('limite,contenido,umbral,codigo',[
    ('profundidad_xml',b'<a><b><c/></b></a>',3,'LIMITE_PROFUNDIDAD'),
    ('elementos_xml',b'<a><b/><c/></a>',3,'LIMITE_ELEMENTOS'),
    ('texto_bytes',b'<a>abc</a>',3,'LIMITE_TEXTO'),
    ('atributo_bytes',b'<a valor="abc"/>',3,'LIMITE_ATRIBUTO'),
])
@pytest.mark.parametrize('desfase',[-1,0,1])
def test_fronteras_xml(tmp_path,limite,contenido,umbral,codigo,desfase):
    ruta=tmp_path/'xml'; ruta.write_bytes(contenido)
    perfil=PerfilEnsayo().model_dump(); perfil[limite]=umbral+desfase
    if desfase==-1:
        with pytest.raises(RechazoArchivo,match=codigo): comprobar_xml(ruta,perfil)
    else: comprobar_xml(ruta,perfil)


@pytest.mark.parametrize('nombre',['../prueba.xml','/prueba.xml','C:/prueba.xml','a\\prueba.xml','a/./prueba.xml','a//prueba.xml'])
def test_zip_ruta_invalida(tmp_path,nombre):
    assert ejecutar(tmp_path,comprimir([(nombre,XML)]),'SINTETICO_ZIP_V1')['codigo']=='ZIP_RUTA_INVALIDA'


@pytest.mark.parametrize('entradas,codigo',[
    ([('uno.xml',XML),('dos.xml',XML)],'ZIP_XML_AMBIGUO'),
    ([('uno.txt',XML)],'ZIP_XML_AMBIGUO'),
    ([('uno.xml',XML),('UNO.XML',XML)],'ZIP_NOMBRE_DUPLICADO'),
    ([('uno.xml',XML),('archivo.zip',b'contenido')],'ZIP_ANIDADO'),
    ([('uno.xml',XML),('archivo.dat',b'PK\x03\x04')],'ZIP_ANIDADO'),
])
def test_zip_rechazado(tmp_path,entradas,codigo):
    assert ejecutar(tmp_path,comprimir(entradas),'SINTETICO_ZIP_V1')['codigo']==codigo


def test_zip_crc_y_cifrado(tmp_path):
    original=comprimir([('uno.xml',XML)])
    alterado=original.replace(b'Empresa ficticia Uno',b'Empresa ficticia Dos')
    assert ejecutar(tmp_path,alterado,'SINTETICO_ZIP_V1')['codigo']=='ZIP_INVALIDO'
    cifrado=bytearray(original)
    for firma,offset in [(b'PK\x03\x04',6),(b'PK\x01\x02',8)]:
        posicion=cifrado.index(firma)+offset; cifrado[posicion] |= 1
    assert ejecutar(tmp_path,bytes(cifrado),'SINTETICO_ZIP_V1')['codigo']=='ZIP_CIFRADO'


@pytest.mark.parametrize('modo',[0o120777,0o010600])
def test_zip_archivo_especial(tmp_path,modo):
    entrada=zipfile.ZipInfo('uno.xml'); entrada.create_system=3; entrada.external_attr=modo<<16
    assert ejecutar(tmp_path,comprimir([(entrada,XML)]),'SINTETICO_ZIP_V1')['codigo']=='ZIP_ARCHIVO_ESPECIAL'


def test_zip64_y_metodo(tmp_path):
    entrada=zipfile.ZipInfo('uno.xml'); entrada.extra=struct.pack('<HHQQ',1,16,len(XML),len(XML))
    assert ejecutar(tmp_path,comprimir([(entrada,XML)]),'SINTETICO_ZIP_V1')['codigo']=='ZIP64_NO_SOPORTADO'
    assert ejecutar(tmp_path,comprimir([('uno.xml',XML)],zipfile.ZIP_BZIP2),'SINTETICO_ZIP_V1')['codigo']=='ZIP_METODO_NO_SOPORTADO'


@pytest.mark.parametrize('desfase',[-1,0,1])
def test_fronteras_zip_y_original(tmp_path,desfase):
    archivo=comprimir([('uno.xml',XML)])
    for limite,umbral in [('entradas_zip',1),('expandido_bytes',len(XML)),('relacion_compresion',1),('recibido_bytes',len(archivo))]:
        resultado=ejecutar(tmp_path,archivo,'SINTETICO_ZIP_V1',**{limite:umbral+desfase})
        assert (resultado['resultado']=='VALIDO') == (desfase>=0), (limite,resultado)


def test_adicionales_inventariados_y_formato_falso(tmp_path):
    archivo=comprimir([('uno.xml',XML),('nota.txt',b'nota ficticia')])
    resultado=ejecutar(tmp_path,archivo,'SINTETICO_ZIP_V1')
    assert resultado['resultado']=='VALIDO' and len(resultado['entradas'])==2
    assert resultado['entradas'][1]['sha256']==hashlib.sha256(b'nota ficticia').hexdigest()
    assert ejecutar(tmp_path,archivo)['codigo']=='FORMATO_INCORRECTO'
    assert ejecutar(tmp_path,XML,'SINTETICO_ZIP_V1')['codigo']=='FORMATO_INCORRECTO'


def test_esquema_alterado_no_se_usa(tmp_path,monkeypatch):
    import infrastructure.listas.validacion_archivo as modulo
    ruta=tmp_path/'esquema.xsd'; ruta.write_text('<invalido/>')
    monkeypatch.setattr(modulo,'ESQUEMA',ruta)
    assert ejecutar(tmp_path)['codigo']=='ESQUEMA_ALTERADO'


@pytest.mark.parametrize('entradas',[
    [('carpeta',b'nota'),('carpeta/uno.xml',XML)],
    [('carpeta/uno.xml',XML),('carpeta',b'nota')],
])
def test_colisiones_archivo_directorio(tmp_path,entradas):
    assert ejecutar(tmp_path,comprimir(entradas),'SINTETICO_ZIP_V1')['codigo']=='ZIP_RUTA_CONFLICTIVA'


def test_xml_no_abre_archivo_externo(tmp_path):
    import os
    import subprocess
    import sys
    import json
    fifo=tmp_path/'secreto'; os.mkfifo(fifo)
    # Leer este recurso bloquearía. El proceso real debe rechazarlo antes de abrirlo.
    original=tmp_path/'original.bin'
    original.write_text(f'<!DOCTYPE lista [<!ENTITY secreto SYSTEM "{fifo.as_uri()}">]><lista>&secreto;</lista>')
    (tmp_path/'solicitud.json').write_text(json.dumps({'formato':'SINTETICO_XML_V1','perfil':PerfilEnsayo().model_dump()}))
    raiz_backend=str(Path(__file__).resolve().parents[2]/'backend')
    respuesta=subprocess.run([sys.executable,'-m','infrastructure.listas.proceso_validacion',str(tmp_path)],timeout=5,
        env=dict(os.environ,PYTHONPATH=raiz_backend))
    assert respuesta.returncode==0
    assert json.loads((tmp_path/'informe.json').read_text())['codigo']=='DTD_PROHIBIDO'


def test_xml_no_solicita_red_ni_xsd_recibido(tmp_path):
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    solicitudes=[]
    class Servidor(BaseHTTPRequestHandler):
        def do_GET(self):
            solicitudes.append(self.path); self.send_response(200); self.end_headers()
        def log_message(self,*_): pass
    servidor=HTTPServer(('127.0.0.1',0),Servidor)
    hilo=threading.Thread(target=servidor.serve_forever,daemon=True); hilo.start()
    direccion=f'http://127.0.0.1:{servidor.server_port}/externo'
    try:
        externo=f'<!DOCTYPE lista SYSTEM "{direccion}"><lista/>'.encode()
        assert ejecutar(tmp_path,externo)['codigo']=='DTD_PROHIBIDO'
        xml=XML.replace(b'sintetica="true"',f'sintetica="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:sagrilaft:pruebas:listas:v1 {direccion}"'.encode())
        assert ejecutar(tmp_path,xml)['resultado']=='VALIDO'
        assert solicitudes==[]
    finally:
        servidor.shutdown(); servidor.server_close(); hilo.join(timeout=2)


def test_resolucion_xsd_externa_prohibida():
    from lxml import etree
    from infrastructure.listas.validacion_archivo import parser_seguro
    esquema=b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:include schemaLocation="file:///archivo-externo.xsd"/></xs:schema>'
    with pytest.raises((RechazoArchivo,etree.XMLSchemaParseError)):
        etree.XMLSchema(etree.fromstring(esquema,parser_seguro()))


def test_dtd_utf16_y_expansion_de_entidades(tmp_path):
    xml='<!DOCTYPE lista [<!ENTITY a "texto"><!ENTITY b "&a;&a;">]><lista>&b;</lista>'
    assert ejecutar(tmp_path,xml.encode('utf-16'))['codigo']=='DTD_PROHIBIDO'


def test_zip_bomba_y_colision_unicode(tmp_path):
    bomba=comprimir([('uno.xml',b'x'*1000000)],zipfile.ZIP_DEFLATED)
    assert ejecutar(tmp_path,bomba,'SINTETICO_ZIP_V1')['codigo']=='LIMITE_RELACION'
    colision=comprimir([('á.xml',XML),('a\u0301.xml',XML)])
    assert ejecutar(tmp_path,colision,'SINTETICO_ZIP_V1')['codigo']=='ZIP_NOMBRE_DUPLICADO'


def test_zip_tamano_declarado_alterado(tmp_path):
    contenido=bytearray(comprimir([('uno.xml',XML)]))
    posicion=contenido.index(b'PK\x01\x02')
    struct.pack_into('<I',contenido,posicion+24,1)
    assert ejecutar(tmp_path,bytes(contenido),'SINTETICO_ZIP_V1')['resultado']=='INVALIDO'


def test_informe_no_admite_exito_incompleto():
    from pydantic import ValidationError
    from domain.listas.administracion import InformeValidacionArchivo
    with pytest.raises(ValidationError):
        InformeValidacionArchivo(resultado='VALIDO',version_validador='ensayo',perfil='f5-sintetico-v1',
            oficial=False,original_sha256='a'*64,esquema_sha256='b'*64,formato='SINTETICO_XML_V1')
