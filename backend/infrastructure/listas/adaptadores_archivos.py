"""Catálogo abierto de adaptadores: una fuente nueva se registra aquí (vía
`registrar_adaptador`), sin tocar la orquestación (admisión, importación,
administración), que ya opera de forma genérica por `fuente_id`/código."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
from domain.listas.administracion import PerfilEnsayo, PerfilOfacLocal


@dataclass(frozen=True)
class AdaptadorArchivo:
    fuente: str
    formato: str
    formatos_recepcion: tuple[str, ...]
    esquema: Path
    huella_esquema: str
    version_esquema: str
    version_validador: str
    version_importador: str
    version_normalizador: str
    perfil: object
    validar_xml: Callable
    registros: Callable
    proyeccion: Callable
    oficial: bool = False
    comparacion_por_referencia: bool = False


def _fabrica_sintetico():
    from infrastructure.listas import validacion_archivo as validacion
    from infrastructure.listas import importador_sintetico as sintetico
    return AdaptadorArchivo('ofac_sdn_prueba', 'SINTETICO_XML_V1',
        ('SINTETICO_XML_V1', 'SINTETICO_ZIP_V1'), validacion.ESQUEMA,
        validacion.HUELLA_ESQUEMA, 'sintetico-v1', validacion.VERSION_VALIDADOR,
        sintetico.VERSION_IMPORTADOR, sintetico.VERSION_NORMALIZADOR, PerfilEnsayo(),
        validacion.validar_xml, sintetico.registros, sintetico.proyeccion)


def _fabrica_ofac():
    from infrastructure.listas import adaptador_ofac as ofac
    return AdaptadorArchivo('ofac_sdn', 'OFAC_ADVANCED_XML_V3',
        ('OFAC_ADVANCED_XML_V3', 'OFAC_ADVANCED_ZIP_V3'), ofac.ESQUEMA,
        ofac.HUELLA_ESQUEMA, 'ofac-advanced-v3-83c7adde', 'ofac-advanced-v1',
        'ofac-advanced-v1', 'nfc-v1', PerfilOfacLocal(),
        ofac.validar_xml, ofac.registros, ofac.proyeccion, True, True)


# Mapa formato -> fábrica (sin argumentos) del `AdaptadorArchivo` correspondiente.
# Las fábricas hacen sus imports de forma perezosa (como antes) para no cargar
# el parser de una fuente que no se está usando. OFAC y el sintético de pruebas
# quedan registrados aquí como dos fuentes más del catálogo, no como casos
# especiales de la función `obtener_adaptador`.
_REGISTRO: dict[str, Callable[[], AdaptadorArchivo]] = {
    'SINTETICO_XML_V1': _fabrica_sintetico,
    'SINTETICO_ZIP_V1': _fabrica_sintetico,
    'OFAC_ADVANCED_XML_V3': _fabrica_ofac,
    'OFAC_ADVANCED_ZIP_V3': _fabrica_ofac,
}


def registrar_adaptador(fuente, formatos, fabrica, oficial=False, procedencia_oficial=None):
    """Da de alta una fuente nueva, en un solo paso, en los dos catálogos:

    - el técnico de aquí (formato -> fábrica del `AdaptadorArchivo`: parser,
      esquema, perfil de límites), y
    - el de hechos de dominio (`domain.listas.catalogo_fuentes`), que valida
      los contratos de recepción (`RecepcionPropuesta`) sin conocer parsers.

    Registrarlos juntos evita que ambos catálogos se desincronicen. `formatos`
    es el/los código(s) de formato de recepción que identifican a esa fuente
    (los que acompañan el archivo al reservarlo); `fabrica` es un callable sin
    argumentos que construye su `AdaptadorArchivo` (mismo contrato que
    `_fabrica_ofac`/`_fabrica_sintetico`). Incorporar una fuente así no
    requiere modificar `obtener_adaptador` ni ningún servicio de admisión,
    importación o administración, que ya resuelven por código de
    fuente/formato de forma genérica.
    """
    from domain.listas.catalogo_fuentes import FuenteConocida, registrar_fuente
    formatos = tuple(formatos)
    for formato in formatos:
        if formato in _REGISTRO:
            raise ValueError(f'El formato {formato!r} ya está registrado')
    registrar_fuente(FuenteConocida(fuente, formatos, oficial, procedencia_oficial))
    for formato in formatos:
        _REGISTRO[formato] = fabrica


def obtener_adaptador(formato):
    fabrica = _REGISTRO.get(formato)
    if fabrica is None:
        raise ValueError('Formato de listas no registrado')
    return fabrica()


# Fuente(s) de prueba/sintéticas: siempre disponibles para administración local,
# igual que antes de abrir el catálogo (nunca dependieron de ningún flag).
_FUENTES_PRUEBA_PREDETERMINADAS = ('ofac_sdn_prueba',)


def fuentes_habilitadas():
    configuradas = os.environ.get('LISTAS_ARCHIVOS_FUENTES_HABILITADAS')
    if configuradas is not None:
        fuentes = tuple(c.strip() for c in configuradas.split(',') if c.strip())
        return fuentes or _FUENTES_PRUEBA_PREDETERMINADAS
    # Compatibilidad retro: sin la variable genérica, se conserva exactamente
    # el comportamiento histórico (solo la fuente sintética, más OFAC si
    # LISTAS_OFAC_LOCAL_HABILITADA=true). Permite incorporar fuentes nuevas
    # vía LISTAS_ARCHIVOS_FUENTES_HABILITADAS sin romper despliegues existentes.
    return (*_FUENTES_PRUEBA_PREDETERMINADAS, 'ofac_sdn') if os.environ.get('LISTAS_OFAC_LOCAL_HABILITADA') == 'true' \
        else _FUENTES_PRUEBA_PREDETERMINADAS


def exigir_adaptador_habilitado(adaptador):
    if adaptador.fuente not in fuentes_habilitadas():
        raise PermissionError('La administración local de esta fuente no está habilitada')
