"""OFAC Advanced v3: estructura oficial a registros comunes, sin búsqueda ni decisiones."""
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata
from lxml import etree
from infrastructure.listas.validacion_archivo import comprobar_xml, exigir, parser_seguro, RechazoArchivo

ESPACIO = 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML'
ESQUEMA = Path(__file__).parent / 'esquemas/ofac_advanced_v3/advanced_xml.xsd'
HUELLA_ESQUEMA = '83c7addeee933968567e45ecbe00dd7e85e32af3b01a8c51ce61ef13cacdff51'
GRUPOS = {'Locations', 'IDRegDocuments', 'DistinctParties', 'ProfileRelationships', 'SanctionsEntries', 'SanctionsEntryLinks'}


def nombre(elemento):
    return etree.QName(elemento).localname


def arbol(elemento):
    """Conserva jerarquía, atributos y texto; el original conserva también los bytes XML."""
    return {'etiqueta': nombre(elemento), 'atributos': dict(elemento.attrib),
            'texto': elemento.text if elemento.text and elemento.text.strip() else '',
            'hijos': [arbol(hijo) for hijo in elemento if isinstance(hijo.tag, str)]}


def recorrer(nodo, etiqueta=None):
    if etiqueta is None or nodo['etiqueta'] == etiqueta:
        yield nodo
    for hijo in nodo['hijos']:
        yield from recorrer(hijo, etiqueta)


def texto(nodo, etiqueta):
    return next((n['texto'] for n in recorrer(nodo, etiqueta)), '')


def liberar(elemento):
    elemento.clear()
    while elemento.getprevious() is not None:
        del elemento.getparent()[0]


def validar_xml(ruta, perfil):
    elementos = comprobar_xml(ruta, perfil)
    datos = ESQUEMA.read_bytes()
    exigir(hashlib.sha256(datos).hexdigest() == HUELLA_ESQUEMA, 'ESQUEMA_ALTERADO')
    esquema = etree.XMLSchema(etree.fromstring(datos, parser_seguro()))
    cantidad, perfiles, sdn, fecha = 0, set(), set(), None
    identificadores = set()
    catalogo_sdn = False
    try:
        for evento, elemento in etree.iterparse(str(ruta), schema=esquema, events=('start','end'),
                resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False):
            if evento == 'start':
                if elemento.getparent() is None:
                    exigir(elemento.tag == f'{{{ESPACIO}}}Sanctions' and elemento.get('Version') == '3'
                            and elemento.get('DeltaBaseVersion') is None, 'PRODUCTO_NO_SOPORTADO')
                continue
            tipo = nombre(elemento)
            if tipo == 'List' and elemento.get('ID') == '1550':
                catalogo_sdn = (elemento.text or '').strip() == 'SDN List'
            if tipo == 'DateOfIssue':
                exigir(elemento.get('CalendarTypeID') == '1', 'CALENDARIO_NO_SOPORTADO')
                valores = [elemento.findtext(f'{{{ESPACIO}}}{parte}') for parte in ('Year','Month','Day')]
                exigir(all(valores), 'FECHA_PUBLICACION_INCOMPLETA')
                fecha = date(*map(int, valores)).isoformat()
            if tipo == 'Profile':
                perfiles.add(elemento.get('ID'))
            if tipo == 'DistinctParty':
                identificador = elemento.get('FixedRef', '')
                exigir(bool(identificador.strip()) and len(identificador) <= 200, 'UID_INVALIDO')
                exigir(identificador not in identificadores, 'UID_DUPLICADO')
                identificadores.add(identificador)
                cantidad += 1
            if tipo == 'SanctionsEntry' and elemento.get('ListID') == '1550':
                sdn.add(elemento.get('ProfileID'))
            # La fecha necesita sus hijos. XSD verifica claves y referencias aun con liberación por flujo.
            if tipo not in {'Year', 'Month', 'Day'} or nombre(elemento.getparent()) != 'DateOfIssue':
                liberar(elemento)
        exigir(cantidad > 0 and perfiles == sdn and catalogo_sdn, 'PRODUCTO_NO_SDN')
    except (etree.XMLSyntaxError, ValueError) as error:
        if isinstance(error, RechazoArchivo):
            raise
        raise RechazoArchivo('XSD_INVALIDO') from error
    return {'registros': cantidad, 'elementos': elementos, 'publicada_en': fecha, 'origen_fecha': 'DATE_OF_ISSUE'}


@contextmanager
def indice(archivo):
    """Índice temporal privado. Evita cargar los 123 MB y sus relaciones completos en memoria."""
    # SQLite crea un temporal privado sin enlace de directorio en Linux: SIGKILL
    # libera el descriptor y el almacenamiento, sin depender de ejecutar finally.
    conexion = sqlite3.connect('')
    try:
        conexion.execute('PRAGMA max_page_count=131072')
        conexion.executescript('''
            CREATE TABLE objeto(tipo TEXT, id TEXT, datos TEXT, PRIMARY KEY(tipo,id));
            CREATE TABLE vinculo(tipo TEXT, titular TEXT, id TEXT);
            CREATE INDEX ix_vinculo ON vinculo(tipo,titular);
            CREATE TABLE perfil(id TEXT PRIMARY KEY, uid TEXT);
        ''')
        catalogos = {}
        archivo.seek(0)
        for _, elemento in etree.iterparse(archivo, events=('end',), resolve_entities=False,
                load_dtd=False, no_network=True, huge_tree=False):
            padre = elemento.getparent()
            tipo = nombre(elemento)
            if tipo == 'ReferenceValueSets':
                for nodo in elemento.iter():
                    if nodo.get('ID') is not None:
                        catalogos[(nombre(nodo), nodo.get('ID'))] = arbol(nodo)
                liberar(elemento)
            elif padre is not None and nombre(padre) in GRUPOS:
                identificador = elemento.get('FixedRef') if tipo == 'DistinctParty' else elemento.get('ID')
                conexion.execute('INSERT INTO objeto VALUES (?,?,?)', (tipo, identificador, json.dumps(arbol(elemento), ensure_ascii=False)))
                if tipo == 'DistinctParty':
                    for perfil in elemento.findall(f'{{{ESPACIO}}}Profile'):
                        conexion.execute('INSERT INTO perfil VALUES (?,?)', (perfil.get('ID'), identificador))
                campos = {'IDRegDocument': ['IdentityID'], 'SanctionsEntry': ['ProfileID'],
                          'ProfileRelationship': ['From-ProfileID'],
                          'SanctionsEntryLink': ['EntryA-SanctionsEntryID', 'EntryB-SanctionsEntryID']}.get(tipo, [])
                for campo in campos:
                    conexion.execute('INSERT INTO vinculo VALUES (?,?,?)', (tipo, elemento.get(campo), identificador))
                liberar(elemento)
        conexion.commit()
        yield conexion, catalogos
    finally:
        conexion.close()


def obtener(conexion, tipo, identificador):
    fila = conexion.execute('SELECT datos FROM objeto WHERE tipo=? AND id=?', (tipo, identificador)).fetchone()
    if fila is None:
        raise ValueError('Referencia OFAC no resuelta')
    return json.loads(fila[0])


def vinculados(conexion, tipo, titular):
    return [obtener(conexion, tipo, fila[0]) for fila in conexion.execute(
        'SELECT DISTINCT id FROM vinculo WHERE tipo=? AND titular=? ORDER BY id', (tipo, titular))]


def referencias_catalogo():
    """El XSD revisado define qué catálogo corresponde a cada atributo de referencia."""
    datos = ESQUEMA.read_bytes()
    exigir(hashlib.sha256(datos).hexdigest() == HUELLA_ESQUEMA, 'ESQUEMA_ALTERADO')
    esquema = etree.fromstring(datos, parser_seguro())
    ns = {'x': 'http://www.w3.org/2001/XMLSchema'}
    claves = {n.get('name'): n.find('x:selector', ns).get('xpath').split(':')[-1]
              for n in esquema.findall('.//x:key', ns)}
    return {n.find('x:field', ns).get('xpath')[1:]: claves[n.get('refer').split(':')[-1]]
            for n in esquema.findall('.//x:keyref', ns)}


def catalogos_usados(nodos, catalogos, referencias):
    usados = {}
    pendientes = list(nodos)
    while pendientes:
        for nodo in recorrer(pendientes.pop()):
            for atributo, valor in nodo['atributos'].items():
                clave = (referencias.get(atributo), valor)
                if clave in catalogos and clave not in usados:
                    usados[clave] = catalogos[clave]
                    pendientes.append(catalogos[clave])
    return [usados[clave] for clave in sorted(usados)]


def registros(archivo):
    referencias = referencias_catalogo()
    with indice(archivo) as (conexion, catalogos):
        for (datos,) in conexion.execute("SELECT datos FROM objeto WHERE tipo='DistinctParty' ORDER BY rowid"):
            sujeto = json.loads(datos)
            perfiles = list(recorrer(sujeto, 'Profile'))
            documentos, entradas, relaciones, enlaces = [], [], [], []
            for identidad in recorrer(sujeto, 'Identity'):
                documentos.extend(vinculados(conexion, 'IDRegDocument', identidad['atributos']['ID']))
            for perfil in perfiles:
                identificador = perfil['atributos']['ID']
                entradas.extend(vinculados(conexion, 'SanctionsEntry', identificador))
                relaciones.extend(vinculados(conexion, 'ProfileRelationship', identificador))
            for entrada in entradas:
                enlaces.extend(vinculados(conexion, 'SanctionsEntryLink', entrada['atributos']['ID']))
            lugares = set()
            for raiz in [sujeto, *documentos]:
                for nodo in recorrer(raiz):
                    for atributo in ('LocationID', 'IssuedIn-LocationID'):
                        if atributo in nodo['atributos']:
                            lugares.add(nodo['atributos'][atributo])
            ubicaciones = [obtener(conexion, 'Location', identificador) for identificador in sorted(lugares)]
            destinos = {}
            for relacion in relaciones:
                destino = relacion['atributos']['To-ProfileID']
                fila = conexion.execute('SELECT uid FROM perfil WHERE id=?', (destino,)).fetchone()
                if fila is None:
                    raise ValueError('Perfil OFAC de destino no resuelto')
                destinos[destino] = fila[0]
            subtipos = [catalogos[('PartySubType', p['atributos']['PartySubTypeID'])] for p in perfiles]
            clases = {s['atributos']['PartyTypeID'] for s in subtipos}
            clase = {'1': 'PERSONA', '2': 'ENTIDAD', '3': 'LUGAR', '4': 'TRANSPORTE', '5': 'OTRA_ENTIDAD'}
            exigir(len(clases) == 1, 'CLASE_AMBIGUA')
            contexto = [sujeto, *documentos, *entradas, *relaciones, *enlaces, *ubicaciones]
            yield {'uid': sujeto['atributos']['FixedRef'], 'clase': clase.get(next(iter(clases)), 'OTRA_ENTIDAD'),
                   'sujeto': sujeto, 'documentos': documentos, 'ubicaciones': ubicaciones,
                   'sanciones': entradas, 'relaciones': relaciones, 'enlaces': enlaces,
                   'destinos': destinos, 'catalogos': catalogos_usados(contexto, catalogos, referencias)}


def proyeccion(contenido):
    salida = {clave: [] for clave in ('nombres', 'identificadores', 'direcciones', 'atributos', 'relaciones')}
    catalogos = {(n['etiqueta'], n['atributos']['ID']): n for n in contenido['catalogos']}
    for alias in recorrer(contenido['sujeto'], 'Alias'):
        for documento in recorrer(alias, 'DocumentedName'):
            alfabetos = defaultdict(list)
            for parte in recorrer(documento, 'NamePartValue'):
                alfabetos[parte['atributos'].get('ScriptID')].append(parte['texto'])
            for alfabeto, partes in alfabetos.items():
                original = ' '.join(partes)
                exigir(bool(original.strip()), 'NOMBRE_VACIO')
                salida['nombres'].append(dict(original=original, normalizado=unicodedata.normalize('NFC', original),
                    tipo='PRINCIPAL' if alias['atributos'].get('Primary') in ('true', '1') else 'ALIAS',
                    atributos={'alias': alias['atributos'], 'nombre_documentado': documento, 'alfabeto_id': alfabeto}))
    for documento in contenido['documentos']:
        atributos = documento['atributos']
        original = texto(documento, 'IDRegistrationNo')
        pais = catalogos.get(('Country', atributos.get('IssuedBy-CountryID')), {}).get('atributos', {}).get('ISO2')
        salida['identificadores'].append(dict(tipo='OFAC_DOCUMENTO:' + atributos['IDRegDocTypeID'],
            original=original, normalizado=unicodedata.normalize('NFC', original), pais_emisor=pais,
            atributos={'documento': documento}))
    for lugar in contenido['ubicaciones']:
        salida['direcciones'].append(dict(original=lugar, normalizada=lugar))
    for tipo, nodos in [('caracteristica', list(recorrer(contenido['sujeto'], 'Feature'))),
                        ('observacion', list(recorrer(contenido['sujeto'], 'Comment'))),
                        ('sancion', contenido['sanciones']), ('enlace_sancion', contenido['enlaces']),
                        ('catalogo', contenido['catalogos'])]:
        for ordinal, nodo in enumerate(nodos):
            salida['atributos'].append(dict(tipo='OFAC_' + tipo.upper(), valor=nodo,
                referencia_original=f"DistinctParty[{contenido['uid']}]/{tipo}/{ordinal}"))
    for relacion in contenido['relaciones']:
        atributos = relacion['atributos']
        salida['relaciones'].append(dict(identificador_destino=contenido['destinos'][atributos['To-ProfileID']],
            ambito_destino='INTERNO', tipo='OFAC_RELACION:' + atributos['RelationTypeID'], atributos={'relacion': relacion}))
    return salida
