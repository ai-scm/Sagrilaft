"""
Resolución y creación de rutas de almacenamiento por tipo de contraparte.
"""

import re

from domain.excepciones import ContraparteInvalidaError
from domain.formulario.tipos import TipoContraparte


_CARPETA_POR_TIPO: dict[str, str] = {
    TipoContraparte.CLIENTE.value: "CLIENTES",
    TipoContraparte.PROVEEDOR.value: "PROVEEDORES",
}


def resolver_key_contraparte(tipo_contraparte: str, razon_social: str) -> str:
    """
    Devuelve el prefijo de key del backend para los archivos de la contraparte.

    Ejemplo: resolver_key_contraparte('cliente', 'Empresa SA') → 'CLIENTES/Empresa_SA'
    La key es válida tanto para LocalStorage (se convierte en subdirectorio)
    como para S3Storage (se usa como prefijo de objeto).
    """
    tipo = (tipo_contraparte or "").strip().lower()
    carpeta_tipo = _CARPETA_POR_TIPO.get(tipo)
    if not carpeta_tipo:
        raise ContraparteInvalidaError(tipo_contraparte)
    return f"{carpeta_tipo}/{_sanitizar_nombre_carpeta(razon_social)}"


def _sanitizar_nombre_carpeta(nombre: str) -> str:
    nombre = (nombre or "").strip()
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre)
    return nombre or "SIN_NOMBRE"
