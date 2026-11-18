"""F5.1: contratos y reglas sin cargas, base de datos ni importador."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4
import subprocess
import zipfile
import pytest
from pydantic import ValidationError
from domain.listas.administracion import RecepcionPropuesta, PerfilEnsayo, SolicitudAdministrativa
from services.listas.autorizacion_administrativa import exigir_revision, exigir_ejecucion, exigir_entorno_sintetico
from services.listas.politica_v2 import ActorListas


def actor(nombre, permisos=('listas.aprobar_version', 'listas.activar_version')):
    return ActorListas('identidad-local', nombre, frozenset(permisos))


@pytest.mark.parametrize('cargador', ['A', 'B', 'historico'])
def test_restauracion_solo_requiere_solicitante_y_otro_aprobador(cargador):
    exigir_revision(actor('B'), actor('A'), actor(cargador), 'REVERSION')
    exigir_ejecucion(actor('B'), actor('B'), actor('A'), actor(cargador), 'REVERSION')


@pytest.mark.parametrize('tipo', ['ACTIVACION', 'REVERSION'])
def test_solicitante_puede_aprobar(tipo):
    exigir_revision(actor('A'), actor('A'), actor('historico'), tipo)


def test_cargador_puede_aprobar_activacion_inicial():
    exigir_revision(actor('B'), actor('A'), actor('B'), 'ACTIVACION')


def test_ejecutor_debe_ser_aprobador():
    with pytest.raises(PermissionError):
        exigir_ejecucion(actor('C'), actor('B'), actor('A'), actor('historico'), 'REVERSION')


@pytest.mark.parametrize('permisos', [(), ('listas.activar_version',), ('listas.aprobar_version',)])
def test_ejecucion_exige_ambos_permisos(permisos):
    with pytest.raises(PermissionError):
        exigir_ejecucion(actor('B', permisos), actor('B'), actor('A'), actor('A'), 'REVERSION')


@pytest.mark.parametrize('entorno', ['production', 'staging', '', 'desconocido'])
def test_perfil_sintetico_rechaza_entorno_compartido(entorno):
    with pytest.raises(PermissionError):
        exigir_entorno_sintetico(entorno)


@pytest.mark.parametrize('entorno', ['development', 'local', 'test'])
def test_entorno_local(entorno):
    exigir_entorno_sintetico(entorno)


def recepcion():
    return dict(fuente='ofac_sdn_prueba', formato='SINTETICO_XML_V1', nombre_original='v1.xml',
                procedencia='FIXTURE_LOCAL', huella_declarada='a'*64, clave='ensayo-1')


@pytest.mark.parametrize('campo,valor', [('fuente','ofac_sdn'), ('formato','SDN_ADVANCED.XML'), ('huella_declarada','x'), ('actor','administrador'), ('clave','')])
def test_entrada_no_admite_oficial_ni_identidad_cliente(campo, valor):
    datos=recepcion(); datos[campo]=valor
    with pytest.raises(ValidationError): RecepcionPropuesta(**datos)


def test_contratos_validos_y_perfil_explicito():
    assert RecepcionPropuesta(**recepcion()).procedencia == 'FIXTURE_LOCAL'
    assert SolicitudAdministrativa(comparacion_id=uuid4(), politica_id=uuid4(), tipo='REVERSION', motivo='Restaurar ensayo', clave='r1').tipo == 'REVERSION'
    assert PerfilEnsayo().concesion_segundos > PerfilEnsayo().latido_segundos
    with pytest.raises(ValidationError): PerfilEnsayo(memoria_bytes=0)


RAIZ = Path(__file__).resolve().parents[1] / 'fixtures/listas_f5'


def test_originales_manifiesto_y_zip():
    manifiesto=json.loads((RAIZ/'manifiesto.json').read_text())
    assert manifiesto['oficial'] is False
    for nombre, huella in manifiesto['archivos'].items():
        assert hashlib.sha256((RAIZ/nombre).read_bytes()).hexdigest() == huella
    with zipfile.ZipFile(RAIZ/'v1.zip') as archivo:
        assert archivo.read('v1.xml') == (RAIZ/'v1.xml').read_bytes()


def test_paquete_sintetico_xsd_y_referencias():
    # lxml ya disponible en Python del sistema; no se instala ni se importa en backend.
    programa = '''
from lxml import etree
from pathlib import Path
import sys
p=Path(sys.argv[1]); ns={'p':'urn:sagrilaft:pruebas:listas:v1'}
parser=etree.XMLParser(resolve_entities=False,load_dtd=False,no_network=True)
schema=etree.XMLSchema(etree.parse(str(p/'lista_sintetica.xsd'),parser))
for nombre in ('v1.xml','v2.xml'):
    raiz=etree.parse(str(p/nombre),parser)
    schema.assertValid(raiz)
    ids=raiz.xpath('//p:registro/@uid',namespaces=ns)
    assert len(ids)==len(set(ids))==2
    assert set(raiz.xpath('//p:relacion/@destino',namespaces=ns)) <= set(ids)
assert not schema.validate(etree.parse(str(p/'invalido.xml'),parser))
print('XSD sintético: dos válidos y uno inválido comprobados')
'''
    # En CI el Python del sistema no trae lxml: sin él no hay con qué validar el XSD.
    if subprocess.run(['/usr/bin/python3','-c','import lxml'],capture_output=True).returncode != 0:
        pytest.skip('lxml no está instalado en el Python del sistema')
    resultado=subprocess.run(['/usr/bin/python3','-c',programa,str(RAIZ)],capture_output=True,text=True)
    assert resultado.returncode == 0, resultado.stderr


def test_restauracion_no_depende_de_identidad_del_cargador_historico():
    historico = ActorListas('', '', frozenset())
    exigir_ejecucion(actor('B'), actor('B'), actor('A'), historico, 'REVERSION')
    with pytest.raises(PermissionError):
        exigir_revision(actor('B'), actor('A'), historico, 'ACTIVACION')


@pytest.mark.parametrize('valor', [True, 1.0, '1', -1, 9223372036854775808])
def test_revision_se_ajusta_a_bigint_sin_conversiones(valor):
    from domain.listas.administracion import ComparacionPropuesta
    with pytest.raises(ValidationError):
        ComparacionPropuesta(fuente_id=uuid4(), destino_id=uuid4(), revision_esperada=valor, clave='p1')


@pytest.mark.parametrize('estado,fase,conteo,error', [
    ('PENDIENTE','IMPORTACION',0,None), ('PENDIENTE','VALIDACION',1,None),
    ('COMPLETADO','IMPORTACION',2,None), ('COMPLETADO','SELLADO',0,None),
    ('FALLIDO','VALIDACION',0,None), ('EN_CURSO','IMPORTACION',1,'ERROR'),
    ('COMPLETADO','SELLADO',1,'ERROR'), ('FALLIDO','VALIDACION',0,''),
])
def test_progreso_rechaza_resultados_contradictorios(estado, fase, conteo, error):
    from domain.listas.administracion import ProgresoImportacion
    with pytest.raises(ValidationError):
        ProgresoImportacion(intento_id=uuid4(), estado=estado, fase=fase,
                           registros_confirmados=conteo, codigo_error=error)


@pytest.mark.parametrize('estado,fase,conteo,error', [
    ('PENDIENTE','VALIDACION',0,None), ('EN_CURSO','IMPORTACION',1,None),
    ('COMPLETADO','SELLADO',2,None), ('FALLIDO','VALIDACION',0,'XSD_INVALIDO'),
])
def test_progreso_valido(estado, fase, conteo, error):
    from domain.listas.administracion import ProgresoImportacion
    ProgresoImportacion(intento_id=uuid4(), estado=estado, fase=fase,
                       registros_confirmados=conteo, codigo_error=error)


def test_oraculo_de_cambios_corresponde_a_los_archivos():
    # Solo verifica fixtures confiables; no es el parser de recepción de F5.3.
    from xml.etree import ElementTree as ET
    def registros(nombre):
        return {r.attrib['uid']: ET.tostring(r).strip() for r in ET.parse(RAIZ/nombre).getroot()}
    primera, segunda = registros('v1.xml'), registros('v2.xml')
    esperado=json.loads((RAIZ/'esperado.json').read_text())
    assert sorted(segunda.keys()-primera.keys()) == esperado['altas']
    assert sorted(primera.keys()-segunda.keys()) == esperado['bajas']
    assert sorted(k for k in primera.keys() & segunda.keys() if primera[k] != segunda[k]) == esperado['modificados']
    assert len(primera) == esperado['registros_v1']
    assert len(segunda) == esperado['registros_v2']
