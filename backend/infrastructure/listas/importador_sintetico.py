"""Proyección del XML sintético ya validado. No interpreta formatos OFAC."""
import unicodedata
from lxml import etree
from infrastructure.listas.validacion_archivo import ESPACIO
from services.listas.informes import calcular_huella


VERSION_IMPORTADOR = 'sintetico-v1'
VERSION_NORMALIZADOR = 'nfc-v1'


def normalizar(texto):
    return unicodedata.normalize('NFC', texto)


def registros(archivo):
    archivo.seek(0)
    for _, elemento in etree.iterparse(archivo, events=('end',), tag=f'{{{ESPACIO}}}registro',
            resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False):
        contenido = {'uid': elemento.get('uid'), 'clase': elemento.get('clase'), 'campos': [
            {'tipo': etree.QName(hijo).localname, 'texto': hijo.text or '', 'atributos': dict(hijo.attrib)}
            for hijo in elemento]}
        yield contenido
        elemento.clear()
        while elemento.getprevious() is not None:
            del elemento.getparent()[0]


def proyeccion(contenido):
    salida = {'nombres': [], 'identificadores': [], 'direcciones': [], 'atributos': [], 'relaciones': []}
    for campo in contenido['campos']:
        tipo, texto, atributos = campo['tipo'], campo['texto'], campo['atributos']
        if tipo in ('nombre','alias'):
            salida['nombres'].append(dict(original=texto, normalizado=normalizar(texto),
                tipo='PRINCIPAL' if tipo=='nombre' else 'ALIAS', atributos=atributos))
        elif tipo=='identificador':
            salida['identificadores'].append(dict(original=texto, normalizado=normalizar(texto),
                tipo=atributos['tipo'], pais_emisor=atributos.get('pais'), atributos=atributos))
        elif tipo=='direccion':
            salida['direcciones'].append(dict(original={'texto':texto}, normalizada={'texto':normalizar(texto)}))
        elif tipo=='observacion':
            salida['atributos'].append(dict(tipo='observacion', valor={'texto':texto},
                referencia_original=f"registro[@uid='{contenido['uid']}']/observacion"))
        elif tipo=='relacion':
            salida['relaciones'].append(dict(identificador_destino=atributos['destino'],
                ambito_destino='INTERNO', tipo='REFERENCIA', atributos=atributos))
        else:
            raise ValueError('Campo sintético sin mapeo')
    return salida

