"""
Puerto de almacenamiento de archivos.

IAlmacenamiento: contrato que los adaptadores de storage deben cumplir.
InfoDescarga: valor de retorno agnóstico al backend para resolver descargas.

Vive en el dominio para que los servicios dependan solo de esta interfaz,
sin conocer LocalStorage ni S3Storage.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class InfoDescarga:
    """Resultado tipado de resolver un documento para descarga."""
    es_url: bool        # True → RedirectResponse 307; False → FileResponse local
    valor: str          # URL prefirmada (S3) o ruta absoluta local
    nombre_archivo: str
    content_type: str


@runtime_checkable
class IAlmacenamiento(Protocol):
    """
    Puerto de almacenamiento de archivos.

    SOLID-D: los servicios de aplicación dependen de este protocolo,
    no de LocalStorage ni S3Storage.
    """

    def guardar(self, key: str, contenido: bytes, content_type: str = "") -> None: ...
    def leer(self, key: str) -> bytes: ...
    def eliminar(self, key: str) -> None: ...
    def mover(self, key_origen: str, key_destino: str) -> None: ...
    def existe(self, key: str) -> bool: ...
    def guardar_desde_archivo_local(self, key: str, ruta_local: Path, content_type: str = "") -> None: ...
    def info_descarga(self, key: str, nombre_archivo: str, content_type: str) -> InfoDescarga: ...
    def como_archivo_local(self, key: str, nombre: str) -> AbstractContextManager[Path]: ...
