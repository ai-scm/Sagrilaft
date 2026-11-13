"""Caracteriza el catálogo de adaptadores de archivos (OFAC y su sintético de
pruebas), que ahora se resuelven por un registro abierto (`registrar_adaptador`)
en vez de un `if/elif` cerrado. El comportamiento para OFAC/sintético no debe
cambiar; la orquestación (admisión, importación, administración) sigue
operando por código de fuente/formato sin conocer casos especiales.
"""
import pytest

from infrastructure.listas.adaptadores_archivos import (
    exigir_adaptador_habilitado, fuentes_habilitadas, obtener_adaptador, registrar_adaptador,
)


def test_formatos_conocidos_resuelven_su_fuente():
    sintetico = obtener_adaptador('SINTETICO_XML_V1')
    assert sintetico.fuente == 'ofac_sdn_prueba'
    assert sintetico.oficial is False
    assert sintetico.comparacion_por_referencia is False
    assert obtener_adaptador('SINTETICO_ZIP_V1').fuente == 'ofac_sdn_prueba'

    ofac = obtener_adaptador('OFAC_ADVANCED_XML_V3')
    assert ofac.fuente == 'ofac_sdn'
    assert ofac.oficial is True
    assert ofac.comparacion_por_referencia is True
    assert obtener_adaptador('OFAC_ADVANCED_ZIP_V3').fuente == 'ofac_sdn'


def test_formato_no_registrado_falla():
    with pytest.raises(ValueError):
        obtener_adaptador('FORMATO_INEXISTENTE')


def test_fuentes_habilitadas_por_defecto_solo_sintetica(monkeypatch):
    monkeypatch.delenv('LISTAS_OFAC_LOCAL_HABILITADA', raising=False)
    monkeypatch.delenv('LISTAS_ARCHIVOS_FUENTES_HABILITADAS', raising=False)
    assert fuentes_habilitadas() == ('ofac_sdn_prueba',)


def test_fuentes_habilitadas_con_flag_ofac_heredado(monkeypatch):
    monkeypatch.delenv('LISTAS_ARCHIVOS_FUENTES_HABILITADAS', raising=False)
    monkeypatch.setenv('LISTAS_OFAC_LOCAL_HABILITADA', 'true')
    assert fuentes_habilitadas() == ('ofac_sdn_prueba', 'ofac_sdn')


def test_exigir_adaptador_habilitado_respeta_la_lista(monkeypatch):
    monkeypatch.delenv('LISTAS_ARCHIVOS_FUENTES_HABILITADAS', raising=False)
    monkeypatch.delenv('LISTAS_OFAC_LOCAL_HABILITADA', raising=False)
    exigir_adaptador_habilitado(obtener_adaptador('SINTETICO_XML_V1'))
    with pytest.raises(PermissionError):
        exigir_adaptador_habilitado(obtener_adaptador('OFAC_ADVANCED_XML_V3'))


# ---------------------------------------------------------------------------
# Guarda de integridad: el registro abierto no permite pisar por accidente el
# formato de una fuente ya registrada (OFAC o su sintético de pruebas).
# ---------------------------------------------------------------------------

def test_no_se_puede_registrar_dos_veces_el_mismo_formato():
    with pytest.raises(ValueError):
        registrar_adaptador('cualquier_fuente', ('SINTETICO_XML_V1',), lambda: None)
    # El intento fallido no debe haber dejado nada a medio registrar.
    assert obtener_adaptador('SINTETICO_XML_V1').fuente == 'ofac_sdn_prueba'
