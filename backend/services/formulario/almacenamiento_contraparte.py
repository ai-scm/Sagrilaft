"""
Resolución y creación de rutas de almacenamiento por tipo de contraparte.
"""

import re
from pathlib import Path

from domain.excepciones import ContraparteInvalidaError


_CARPETA_POR_TIPO: dict[str, str] = {
    "cliente": "CLIENTES",
    "proveedor": "PROVEEDORES",
}


def resolver_ruta_contraparte(
    tipo_contraparte: str, razon_social: str, upload_dir: Path
) -> Path:
    """Determina el directorio destino según tipo de contraparte y razón social."""
    tipo = (tipo_contraparte or "").strip().lower()
    carpeta_tipo = _CARPETA_POR_TIPO.get(tipo)
    if not carpeta_tipo:
        raise ContraparteInvalidaError(tipo_contraparte)
    return upload_dir / carpeta_tipo / _sanitizar_nombre_carpeta(razon_social)


def crear_carpeta_contraparte(ruta: Path) -> Path:
    """Crea el directorio de la contraparte si no existe. Retorna la ruta."""
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _sanitizar_nombre_carpeta(nombre: str) -> str:
    nombre = (nombre or "").strip()
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre)
    return nombre or "SIN_NOMBRE"
