"""Catálogo de fuentes de archivos conocidas por el dominio.

Vive en el dominio (no en infraestructura) porque son hechos de negocio que
los contratos (Pydantic, en `administracion.py`) deben poder validar sin
depender de la capa de infraestructura: qué formatos pertenecen a qué fuente,
si es oficial y cuál es su procedencia declarada. No contiene parsers ni E/S
— eso sigue siendo responsabilidad exclusiva de
`infrastructure.listas.adaptadores_archivos`.

Las dos fuentes históricas (OFAC y su sintético de pruebas) se registran aquí
mismo, para que este catálogo sea válido por sí solo sin depender de que se
haya importado la capa de infraestructura (p. ej. en tests que solo ejercitan
contratos de dominio). Una fuente nueva se agrega llamando a
`infrastructure.listas.adaptadores_archivos.registrar_adaptador`, que registra
al mismo tiempo el adaptador técnico y los hechos aquí, para que ambos
catálogos no puedan desincronizarse.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FuenteConocida:
    codigo: str
    formatos: tuple[str, ...]
    oficial: bool = False
    procedencia_oficial: str | None = None

    def __post_init__(self):
        if self.oficial and not self.procedencia_oficial:
            raise ValueError('Una fuente oficial requiere procedencia_oficial')
        if not self.formatos:
            raise ValueError('Una fuente requiere al menos un formato')


_POR_CODIGO: dict[str, FuenteConocida] = {}
_POR_FORMATO: dict[str, str] = {}


def registrar_fuente(fuente: FuenteConocida) -> None:
    if fuente.codigo in _POR_CODIGO:
        raise ValueError(f'La fuente {fuente.codigo!r} ya está registrada')
    for formato in fuente.formatos:
        if formato in _POR_FORMATO:
            raise ValueError(f'El formato {formato!r} ya está registrado')
    _POR_CODIGO[fuente.codigo] = fuente
    for formato in fuente.formatos:
        _POR_FORMATO[formato] = fuente.codigo


def fuente_de_formato(formato: str) -> FuenteConocida | None:
    codigo = _POR_FORMATO.get(formato)
    return _POR_CODIGO.get(codigo) if codigo else None


registrar_fuente(FuenteConocida('ofac_sdn_prueba', ('SINTETICO_XML_V1', 'SINTETICO_ZIP_V1'), oficial=False))
registrar_fuente(FuenteConocida('ofac_sdn', ('OFAC_ADVANCED_XML_V3', 'OFAC_ADVANCED_ZIP_V3'), oficial=True,
    procedencia_oficial='https://sanctionslist.ofac.treas.gov/Home/SdnList'))
