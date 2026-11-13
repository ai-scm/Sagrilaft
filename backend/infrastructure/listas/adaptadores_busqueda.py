"""Adaptadores declarados para traducir registros ya importados, sin abrir XML."""
from infrastructure.listas import lectura_ofac_busqueda, lectura_sintetica_busqueda

LECTORES = {
    "SINTETICO_XML_V1": lectura_sintetica_busqueda,
    "OFAC_ADVANCED_XML_V3": lectura_ofac_busqueda,
}


def obtener_lector(formato):
    try:
        return LECTORES[formato]
    except KeyError as error:
        raise ValueError("Formato sin adaptador de representación de búsqueda") from error
