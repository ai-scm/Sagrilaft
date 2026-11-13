"""Custodia local inmutable para pruebas y volúmenes persistentes autorizados."""
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from domain.listas.errores import ErrorIntegridadEvidencia


@dataclass(frozen=True)
class ObjetoCustodiado:
    clave: str
    huella: str
    tamano_bytes: int


class CustodiaLocalListas:
    def __init__(self, directorio: Path):
        self.directorio = directorio.resolve()
        self.directorio.mkdir(parents=True, exist_ok=True, mode=0o700)

    def guardar(self, contenido: bytes) -> ObjetoCustodiado:
        huella = hashlib.sha256(contenido).hexdigest()
        ruta = self.directorio / huella
        descriptor, temporal = tempfile.mkstemp(prefix="recepcion-", dir=self.directorio)
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                archivo.write(contenido)
                archivo.flush()
                os.fsync(archivo.fileno())
            try:
                os.link(temporal, ruta)
            except FileExistsError:
                self.leer(huella, huella, len(contenido))
            descriptor_directorio = os.open(self.directorio, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor_directorio)
            finally:
                os.close(descriptor_directorio)
        finally:
            os.unlink(temporal)
        return ObjetoCustodiado(huella, huella, len(contenido))

    def leer(self, clave: str, huella: str, tamano_bytes: int | None = None) -> bytes:
        if not re.fullmatch(r"[a-f0-9]{64}", clave) or clave != huella:
            raise ErrorIntegridadEvidencia("Clave de evidencia no válida")
        try:
            descriptor = os.open(self.directorio / clave, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as archivo:
                contenido = archivo.read()
        except OSError as error:
            raise ErrorIntegridadEvidencia("No se puede recuperar la evidencia custodiada") from error
        if hashlib.sha256(contenido).hexdigest() != huella or (tamano_bytes is not None and len(contenido) != tamano_bytes):
            raise ErrorIntegridadEvidencia("La evidencia no coincide con su huella o tamaño")
        return contenido
