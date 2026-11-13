"""`RecepcionPropuesta`/`InformeValidacionArchivo` ya no tienen
`fuente`/`formato`/`procedencia`/`perfil` cerrados en `Literal[...]` a OFAC:
validan en runtime contra el catálogo abierto de `domain.listas.catalogo_fuentes`.
Esta prueba caracteriza el comportamiento vigente para OFAC/sintético, que no
debe cambiar.
"""
import pytest
from pydantic import ValidationError

from domain.listas.administracion import InformeValidacionArchivo, RecepcionPropuesta
from domain.listas.catalogo_fuentes import FuenteConocida, fuente_de_formato


def recepcion(**cambios):
    datos = dict(fuente='ofac_sdn_prueba', formato='SINTETICO_XML_V1', nombre_original='v1.xml',
                 procedencia='FIXTURE_LOCAL', huella_declarada='a' * 64, clave='ensayo-1')
    datos.update(cambios)
    return datos


def test_sintetico_sigue_siendo_valido_sin_descarga():
    assert RecepcionPropuesta(**recepcion()).procedencia == 'FIXTURE_LOCAL'


def test_ofac_exige_procedencia_oficial_y_fecha_de_descarga():
    with pytest.raises(ValidationError):
        RecepcionPropuesta(**recepcion(fuente='ofac_sdn', formato='OFAC_ADVANCED_XML_V3',
            procedencia='https://sanctionslist.ofac.treas.gov/Home/SdnList'))
    valida = RecepcionPropuesta(**recepcion(fuente='ofac_sdn', formato='OFAC_ADVANCED_XML_V3',
        procedencia='https://sanctionslist.ofac.treas.gov/Home/SdnList', descargado_en='2026-01-01T00:00:00Z'))
    assert valida.fuente == 'ofac_sdn'


@pytest.mark.parametrize('cambios', [
    dict(fuente='ofac_sdn'),  # formato sintético con fuente oficial: no coinciden
    dict(formato='OFAC_ADVANCED_XML_V3'),  # fuente de prueba con formato oficial: no coinciden
    dict(procedencia='https://otra-url-cualquiera.example'),  # procedencia no declarada por la fuente
    dict(fuente='fuente_jamas_registrada', formato='FORMATO_JAMAS_REGISTRADO'),  # nada registrado
])
def test_combinaciones_incoherentes_siguen_rechazadas(cambios):
    with pytest.raises(ValidationError):
        RecepcionPropuesta(**recepcion(**cambios))


def test_fuente_oficial_exige_procedencia_oficial_declarada():
    with pytest.raises(ValueError):
        FuenteConocida('oficial_sin_url', ('X',), oficial=True)


# ---------------------------------------------------------------------------
# InformeValidacionArchivo: perfil/formato abiertos (antes Literal cerrado a OFAC).
# ---------------------------------------------------------------------------

def informe(**cambios):
    datos = dict(resultado='INVALIDO', codigo='ESQUEMA_ALTERADO', version_validador='ensayo',
                 perfil='f5-sintetico-v1', oficial=False, original_sha256='a' * 64,
                 esquema_sha256='b' * 64, formato='SINTETICO_XML_V1')
    datos.update(cambios)
    return datos


def test_informe_acepta_perfil_y_formato_conocidos():
    assert InformeValidacionArchivo(**informe()).perfil == 'f5-sintetico-v1'
    assert InformeValidacionArchivo(**informe(perfil='ofac-advanced-local-v2', formato='OFAC_ADVANCED_XML_V3')).formato == 'OFAC_ADVANCED_XML_V3'


@pytest.mark.parametrize('perfil', ['OFAC-MAYUSCULAS', 'con espacios', ''])
def test_informe_sigue_exigiendo_un_codigo_de_perfil_bien_formado(perfil):
    with pytest.raises(ValidationError):
        InformeValidacionArchivo(**informe(perfil=perfil))


@pytest.mark.parametrize('formato', ['sdn.xml', 'CON ESPACIOS', ''])
def test_informe_sigue_exigiendo_un_codigo_de_formato_bien_formado(formato):
    with pytest.raises(ValidationError):
        InformeValidacionArchivo(**informe(formato=formato))


# ---------------------------------------------------------------------------
# Guarda de consistencia: el catálogo de dominio (hechos) y el catálogo técnico
# de infraestructura (parsers) no deben desincronizarse para las fuentes
# históricas, que están declaradas por separado en los dos módulos.
# ---------------------------------------------------------------------------

def test_catalogo_de_dominio_coincide_con_el_catalogo_tecnico_para_las_fuentes_historicas():
    from infrastructure.listas.adaptadores_archivos import obtener_adaptador
    for formato in ('SINTETICO_XML_V1', 'OFAC_ADVANCED_XML_V3'):
        tecnico = obtener_adaptador(formato)
        dominio = fuente_de_formato(formato)
        assert dominio is not None
        assert dominio.codigo == tecnico.fuente
        assert dominio.oficial == tecnico.oficial
