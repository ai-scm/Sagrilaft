"""
Verifica que TipoPersona/TipoContraparte (domain/formulario/tipos.py) sean la
única fuente de verdad para esos valores en el backend — en vez de strings
sueltos ("natural", "juridica", "cliente", "proveedor") reescritos en cada
módulo que los necesita.
"""

from domain.formulario.tipos import TipoContraparte, TipoPersona
from domain.formulario.reglas_tipo_persona import purgar_campos_no_aplicables
from domain.utils.mapeo_campos import _normalizar_tipo_persona
from services.formulario.almacenamiento_contraparte import _CARPETA_POR_TIPO, resolver_key_contraparte
from services.formulario.exportacion_pdf import _VALORES_AMIGABLES


def test_carpeta_por_tipo_usa_enum_como_clave():
    assert TipoContraparte.CLIENTE.value in _CARPETA_POR_TIPO
    assert TipoContraparte.PROVEEDOR.value in _CARPETA_POR_TIPO


def test_resolver_key_contraparte_comportamiento_sin_cambios():
    assert resolver_key_contraparte("cliente", "Empresa SA") == "CLIENTES/Empresa SA"
    assert resolver_key_contraparte("proveedor", "Empresa SA") == "PROVEEDORES/Empresa SA"


def test_purgar_campos_no_aplicables_comportamiento_sin_cambios():
    resultado = purgar_campos_no_aplicables(
        {"direccion_residencia": "x", "actividad_clasificacion": "y"},
        TipoPersona.NATURAL.value,
    )
    assert "actividad_clasificacion" not in resultado
    assert "direccion_residencia" in resultado


def test_valores_amigables_usa_enum_como_clave():
    assert _VALORES_AMIGABLES[TipoPersona.JURIDICA.value] == "Jurídica"
    assert _VALORES_AMIGABLES[TipoContraparte.CLIENTE.value] == "Cliente"


def test_normalizar_tipo_persona_devuelve_valores_del_enum():
    assert _normalizar_tipo_persona("Persona Jurídica") == TipoPersona.JURIDICA.value
    assert _normalizar_tipo_persona("Persona Natural") == TipoPersona.NATURAL.value
