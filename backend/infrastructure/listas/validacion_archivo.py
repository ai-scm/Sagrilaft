"""Validador del perfil sintético. No importa registros ni consulta listas."""
import hashlib
from pathlib import Path, PurePosixPath
import stat
import struct
import unicodedata
import zipfile
from xml.parsers import expat
from lxml import etree

ESPACIO = 'urn:sagrilaft:pruebas:listas:v1'
HUELLA_ESQUEMA = 'eb096ab3802e1b58d8d3ed78e747feb14b4219d30d7442ad13e9f18f215736b3'
ESQUEMA = Path(__file__).parent / 'esquemas/sintetico_v1/lista.xsd'
VERSION_VALIDADOR = 'sintetico-v1.0'


class RechazoArchivo(ValueError):
    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


def exigir(condicion, codigo):
    if not condicion:
        raise RechazoArchivo(codigo)


class ResolucionProhibida(etree.Resolver):
    def resolve(self, url, identificador, contexto):
        raise RechazoArchivo('DEPENDENCIA_EXTERNA')


def parser_seguro():
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                             huge_tree=False, recover=False)
    parser.resolvers.add(ResolucionProhibida())
    return parser


def comprobar_xml(ruta, perfil):
    """Primera pasada por flujo: rechaza DTD antes de resolver cualquier entidad."""
    parser = expat.ParserCreate(namespace_separator='}')
    profundidad = []
    elementos = 0

    def inicio(nombre, atributos):
        nonlocal elementos
        elementos += 1
        exigir(elementos <= perfil['elementos_xml'], 'LIMITE_ELEMENTOS')
        profundidad.append(0)
        exigir(len(profundidad) <= perfil['profundidad_xml'], 'LIMITE_PROFUNDIDAD')
        exigir(not nombre.startswith('http://www.w3.org/2001/XInclude}'), 'XINCLUDE_PROHIBIDO')
        for valor in atributos.values():
            exigir(len(valor.encode('utf-8')) <= perfil['atributo_bytes'], 'LIMITE_ATRIBUTO')

    def texto(valor):
        if profundidad:
            profundidad[-1] += len(valor.encode('utf-8'))
            exigir(profundidad[-1] <= perfil['texto_bytes'], 'LIMITE_TEXTO')

    def prohibido(*_):
        raise RechazoArchivo('DTD_PROHIBIDO')

    parser.StartElementHandler = inicio
    parser.EndElementHandler = lambda _: profundidad.pop()
    parser.CharacterDataHandler = texto
    parser.StartDoctypeDeclHandler = prohibido
    parser.ExternalEntityRefHandler = prohibido
    try:
        with ruta.open('rb') as archivo:
            while bloque := archivo.read(65536):
                parser.Parse(bloque, False)
            parser.Parse(b'', True)
    except expat.ExpatError as error:
        raise RechazoArchivo('XML_MAL_FORMADO') from error
    return elementos


def validar_xml(ruta, perfil):
    elementos = comprobar_xml(ruta, perfil)
    esquema_bytes = ESQUEMA.read_bytes()
    exigir(hashlib.sha256(esquema_bytes).hexdigest() == HUELLA_ESQUEMA, 'ESQUEMA_ALTERADO')
    # El paquete v1 es cerrado y no tiene imports/includes. Un paquete nuevo exige revisión.
    esquema = etree.XMLSchema(etree.fromstring(esquema_bytes, parser_seguro()))
    try:
        with ruta.open('rb') as archivo:
            documento = etree.parse(archivo, parser_seguro())
        raiz = documento.getroot()
        exigir(raiz.tag == f'{{{ESPACIO}}}lista' and raiz.get('sintetica') == 'true', 'PRODUCTO_NO_SOPORTADO')
        exigir(esquema.validate(documento), 'XSD_INVALIDO')
    except etree.XMLSyntaxError as error:
        raise RechazoArchivo('XML_MAL_FORMADO') from error
    registros = raiz.findall(f'{{{ESPACIO}}}registro')
    identificadores = {registro.get('uid') for registro in registros}
    exigir(len(identificadores) == len(registros), 'UID_DUPLICADO')
    for registro in registros:
        exigir(bool(registro.findtext(f'{{{ESPACIO}}}nombre', '').strip()), 'NOMBRE_VACIO')
        for relacion in registro.findall(f'{{{ESPACIO}}}relacion'):
            exigir(relacion.get('destino') in identificadores, 'REFERENCIA_ROTA')
    return {'registros': len(registros), 'elementos': elementos}


def sin_zip64(extra):
    while extra:
        exigir(len(extra) >= 4, 'ZIP_EXTRA_INVALIDO')
        tipo, longitud = struct.unpack('<HH', extra[:4])
        exigir(tipo != 1, 'ZIP64_NO_SOPORTADO')
        exigir(len(extra) >= 4 + longitud, 'ZIP_EXTRA_INVALIDO')
        extra = extra[4 + longitud:]


def extraer_zip(original, destino, perfil):
    inventario, nombres, principales = [], {}, []
    total = comprimido = 0
    with zipfile.ZipFile(original) as archivo, original.open('rb') as crudo:
        crudo.seek(max(0, original.stat().st_size - 65557))
        final = crudo.read()
        posicion_final = final.rfind(b'PK\x05\x06')
        exigir(posicion_final < 20 or final[posicion_final-20:posicion_final-16] != b'PK\x06\x07', 'ZIP64_NO_SOPORTADO')
        exigir(len(archivo.infolist()) <= perfil['entradas_zip'], 'LIMITE_ENTRADAS')
        for entrada in archivo.infolist():
            nombre = entrada.orig_filename
            partes = PurePosixPath(nombre).parts
            normalizado = unicodedata.normalize('NFC', nombre).casefold()
            exigir(nombre and '\x00' not in nombre and '\\' not in nombre and ':' not in nombre
                   and not nombre.startswith('/') and '..' not in partes and '.' not in nombre.split('/')
                   and '//' not in nombre, 'ZIP_RUTA_INVALIDA')
            exigir(normalizado not in nombres, 'ZIP_NOMBRE_DUPLICADO')
            normalizado = normalizado.rstrip('/')
            exigir(normalizado not in nombres, 'ZIP_NOMBRE_DUPLICADO')
            exigir(not any('/'.join(normalizado.split('/')[:i]) in nombres and not nombres['/'.join(normalizado.split('/')[:i])]
                    for i in range(1, len(normalizado.split('/')))), 'ZIP_RUTA_CONFLICTIVA')
            exigir(entrada.is_dir() or not any(n.startswith(normalizado + '/') for n in nombres), 'ZIP_RUTA_CONFLICTIVA')
            nombres[normalizado] = entrada.is_dir()
            modo = entrada.external_attr >> 16
            exigir(stat.S_IFMT(modo) in (0, stat.S_IFREG, stat.S_IFDIR), 'ZIP_ARCHIVO_ESPECIAL')
            exigir(not entrada.flag_bits & 1, 'ZIP_CIFRADO')
            exigir(entrada.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'ZIP_METODO_NO_SOPORTADO')
            exigir(entrada.extract_version < 45, 'ZIP64_NO_SOPORTADO')
            sin_zip64(entrada.extra)
            crudo.seek(entrada.header_offset)
            cabecera = crudo.read(30)
            exigir(len(cabecera) == 30 and cabecera[:4] == b'PK\x03\x04', 'ZIP_CABECERA_INVALIDA')
            longitud_nombre, longitud_extra = struct.unpack('<HH', cabecera[26:30])
            crudo.read(longitud_nombre)
            sin_zip64(crudo.read(longitud_extra))
            if entrada.is_dir():
                exigir(entrada.file_size == 0, 'ZIP_DIRECTORIO_INVALIDO')
                continue
            exigir(entrada.file_size <= perfil['expandido_bytes'], 'LIMITE_EXPANSION')
            exigir(entrada.file_size <= max(entrada.compress_size, 1) * perfil['relacion_compresion'], 'LIMITE_RELACION')
            es_xml = nombre.lower().endswith('.xml')
            exigir(not nombre.lower().endswith(('.zip', '.gz', '.7z', '.tar')), 'ZIP_ANIDADO')
            huella, cantidad, prefijo = hashlib.sha256(), 0, b''
            # Nunca usar el nombre recibido como ruta de salida.
            with (destino.open('wb') if es_xml and not principales else open('/dev/null', 'wb')) as salida:
                with archivo.open(entrada) as contenido:
                    while bloque := contenido.read(65536):
                        prefijo = (prefijo + bloque)[:4]
                        cantidad += len(bloque)
                        total += len(bloque)
                        exigir(total <= perfil['expandido_bytes'], 'LIMITE_EXPANSION')
                        exigir(cantidad <= max(entrada.compress_size, 1) * perfil['relacion_compresion'], 'LIMITE_RELACION')
                        huella.update(bloque)
                        salida.write(bloque)
            exigir(not prefijo.startswith((b'PK', b'\x1f\x8b')), 'ZIP_ANIDADO')
            exigir(cantidad == entrada.file_size, 'ZIP_TAMANO_INVALIDO')
            comprimido += entrada.compress_size
            inventario.append({'nombre': nombre, 'sha256': huella.hexdigest(), 'tamano': cantidad,
                               'principal': es_xml})
            if es_xml:
                principales.append(nombre)
        exigir(len(principales) == 1, 'ZIP_XML_AMBIGUO')
        exigir(total <= max(comprimido, 1) * perfil['relacion_compresion'], 'LIMITE_RELACION')
    return inventario


def validar(original, directorio, formato, perfil):
    from infrastructure.listas.adaptadores_archivos import obtener_adaptador
    adaptador = obtener_adaptador(formato)
    informe = {'version_validador': adaptador.version_validador, 'perfil': perfil['codigo'],
               'esquema_sha256': adaptador.huella_esquema, 'oficial': adaptador.oficial,
               'lxml': etree.LXML_VERSION, 'libxml': etree.LIBXML_VERSION}
    try:
        exigir(original.stat().st_size <= perfil['recibido_bytes'], 'LIMITE_ORIGINAL')
        with original.open('rb') as entrada:
            firma = entrada.read(4)
        if formato in ('SINTETICO_ZIP_V1', 'OFAC_ADVANCED_ZIP_V3'):
            exigir(firma == b'PK\x03\x04', 'FORMATO_INCORRECTO')
            contenido = directorio / 'contenido.xml'
            informe['entradas'] = extraer_zip(original, contenido, perfil)
        else:
            exigir(formato == adaptador.formato and not firma.startswith(b'PK'), 'FORMATO_INCORRECTO')
            contenido = original
            informe['entradas'] = []
        informe.update(adaptador.validar_xml(contenido, perfil))
        huella = hashlib.sha256()
        with contenido.open('rb') as entrada:
            while bloque := entrada.read(65536): huella.update(bloque)
        informe.update(resultado='VALIDO', contenido_sha256=huella.hexdigest(),
                       contenido_tamano=contenido.stat().st_size)
    except RechazoArchivo as error:
        informe.update(resultado='INVALIDO', codigo=error.codigo)
    except (zipfile.BadZipFile, EOFError, RuntimeError):
        informe.update(resultado='INVALIDO', codigo='ZIP_INVALIDO')
    return informe
