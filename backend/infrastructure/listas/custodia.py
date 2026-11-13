"""Custodia inmutable de evidencias de listas: local (desarrollo y pruebas) o S3 (ambientes compartidos)."""
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


class CustodiaS3Listas:
    """Custodia en S3 para ambientes compartidos (ECS no tiene disco persistente).

    Misma regla que la local: la clave es la huella SHA-256 del contenido, guardar es
    idempotente y leer verifica huella y tamaño. Los objetos viven bajo un prefijo propio
    y nunca se exponen con URL prefirmadas: el backend los entrega tras comprobar permisos.
    Solo cubre `guardar` y `leer`; la administración de listas (recepción, validación e
    importación) usa disco y sigue limitada al entorno local.
    """

    def __init__(self, bucket: str, prefijo: str = "listas/custodia/", cliente=None, region: str | None = None):
        if not bucket:
            raise ValueError("Falta el bucket de custodia de listas")
        if not prefijo.endswith("/") or prefijo.startswith("/"):
            raise ValueError("El prefijo de custodia debe terminar en '/' y no empezar por '/'")
        self.bucket, self.prefijo = bucket, prefijo
        if cliente is None:
            import boto3
            cliente = boto3.client("s3", region_name=region)
        self._s3 = cliente

    def _clave(self, huella: str) -> str:
        return f"{self.prefijo}{huella}"

    def guardar(self, contenido: bytes) -> ObjetoCustodiado:
        huella = hashlib.sha256(contenido).hexdigest()
        self._s3.put_object(Bucket=self.bucket, Key=self._clave(huella), Body=contenido,
                            ContentType="application/octet-stream", ChecksumSHA256=_base64_sha256(contenido),
                            ServerSideEncryption="AES256")
        return ObjetoCustodiado(huella, huella, len(contenido))

    def leer(self, clave: str, huella: str, tamano_bytes: int | None = None) -> bytes:
        if not re.fullmatch(r"[a-f0-9]{64}", clave) or clave != huella:
            raise ErrorIntegridadEvidencia("Clave de evidencia no válida")
        try:
            contenido = self._s3.get_object(Bucket=self.bucket, Key=self._clave(clave))["Body"].read()
        except Exception as error:  # botocore.ClientError, red o credenciales: la evidencia no está disponible.
            raise ErrorIntegridadEvidencia("No se puede recuperar la evidencia custodiada") from error
        if hashlib.sha256(contenido).hexdigest() != huella or (tamano_bytes is not None and len(contenido) != tamano_bytes):
            raise ErrorIntegridadEvidencia("La evidencia no coincide con su huella o tamaño")
        return contenido


def _base64_sha256(contenido: bytes) -> str:
    import base64
    return base64.b64encode(hashlib.sha256(contenido).digest()).decode()


def custodia_desde_entorno():
    """Custodia según el entorno: S3 si LISTAS_CUSTODIA_BACKEND=s3, si no el directorio local."""
    backend = os.getenv("LISTAS_CUSTODIA_BACKEND", "local").strip().lower()
    if backend == "s3":
        return CustodiaS3Listas(os.getenv("S3_BUCKET", "").strip(),
                                os.getenv("LISTAS_CUSTODIA_S3_PREFIJO", "listas/custodia/").strip(),
                                region=os.getenv("AWS_REGION") or None)
    if backend != "local":
        raise ValueError("LISTAS_CUSTODIA_BACKEND debe ser local o s3")
    directorio = os.getenv("LISTAS_CUSTODIA_DIRECTORIO")
    if not directorio:
        return None
    return CustodiaLocalListas(Path(directorio))
