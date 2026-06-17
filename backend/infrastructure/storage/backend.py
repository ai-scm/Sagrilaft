"""
Implementaciones de almacenamiento de archivos.

LocalStorage : archivos en disco (desarrollo y servidores sin S3).
S3Storage    : objetos en Amazon S3 (producción en AWS).

El campo ruta_archivo en DocumentoAdjunto y ruta_documento_firmado en Formulario
almacenan KEYS relativas (ej. 'CLIENTES/Empresa_SA/rut.pdf'), no rutas absolutas.

El protocolo IAlmacenamiento vive en domain/puertos/almacenamiento.py.
"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga


class LocalStorage:
    """Guarda archivos en el disco del servidor — sin dependencias externas."""

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)

    def _ruta(self, key: str) -> Path:
        return self._base / key

    def ruta_local(self, key: str) -> Path:
        """Ruta absoluta en disco. Solo disponible en LocalStorage."""
        return self._ruta(key)

    def guardar(self, key: str, contenido: bytes, content_type: str = "") -> None:
        ruta = self._ruta(key)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)

    def leer(self, key: str) -> bytes:
        return self._ruta(key).read_bytes()

    def eliminar(self, key: str) -> None:
        ruta = self._ruta(key)
        if ruta.exists():
            ruta.unlink()

    def mover(self, key_origen: str, key_destino: str) -> None:
        origen = self._ruta(key_origen)
        destino = self._ruta(key_destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.exists():
            shutil.move(str(origen), str(destino))

    def limpiar_directorio_vacio(self, key: str) -> None:
        """Intenta eliminar el directorio si está vacío."""
        import logging
        logger = logging.getLogger(__name__)
        
        directorio = self._ruta(key)
        logger.info(f"[CLEANUP] Intentando limpiar: {directorio}")
        
        if not directorio.exists():
            logger.info(f"[CLEANUP] El directorio no existe: {directorio}")
            return
            
        # Verifica el contenido del directorio antes de intentar eliminar
        contenido = list(directorio.iterdir())
        if contenido:
            logger.warning(f"[CLEANUP] El directorio NO está vacío ({len(contenido)} items): {directorio}")
            for item in contenido:
                logger.warning(f"[CLEANUP]   - {item.name}")
            return
        
        try:
            directorio.rmdir()
            logger.info(f"[CLEANUP] Directorio eliminado exitosamente: {directorio}")
        except OSError as e:
            logger.error(f"[CLEANUP] Error al eliminar {directorio}: {e}")
        except FileNotFoundError:
            logger.info(f"[CLEANUP] El directorio no existe (ya fue eliminado): {directorio}")

    def existe(self, key: str) -> bool:
        return self._ruta(key).exists()

    def guardar_desde_archivo_local(self, key: str, ruta_local: Path, content_type: str = "") -> None:
        destino = self._ruta(key)
        if ruta_local.resolve() != destino.resolve():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ruta_local), str(destino))

    def info_descarga(self, key: str, nombre_archivo: str, content_type: str) -> InfoDescarga:
        return InfoDescarga(
            es_url=False,
            valor=str(self._ruta(key)),
            nombre_archivo=nombre_archivo,
            content_type=content_type,
        )

    @contextmanager
    def como_archivo_local(self, key: str, nombre: str) -> Generator[Path, None, None]:
        """Entrega la ruta real en disco sin necesidad de copia temporal."""
        yield self._ruta(key)


class S3Storage:
    """Guarda archivos en Amazon S3 — producción en AWS."""

    def __init__(self, bucket: str, region: str) -> None:
        import boto3
        self._bucket = bucket
        self._s3 = boto3.client("s3", region_name=region)

    def guardar(self, key: str, contenido: bytes, content_type: str = "") -> None:
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": contenido}
        if content_type:
            kwargs["ContentType"] = content_type
        self._s3.put_object(**kwargs)

    def leer(self, key: str) -> bytes:
        respuesta = self._s3.get_object(Bucket=self._bucket, Key=key)
        return respuesta["Body"].read()

    def eliminar(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)

    def mover(self, key_origen: str, key_destino: str) -> None:
        self._s3.copy_object(
            Bucket=self._bucket,
            Key=key_destino,
            CopySource={"Bucket": self._bucket, "Key": key_origen},
        )
        self._s3.delete_object(Bucket=self._bucket, Key=key_origen)

    def limpiar_directorio_vacio(self, key: str) -> None:
        """En S3 no hay directorios reales — sin-op."""
        pass

    def existe(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            # 404 / NoSuchKey → el objeto no existe
            # Cualquier otro código (403 AccessDenied, 5xx, etc.) es un error real
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def guardar_desde_archivo_local(self, key: str, ruta_local: Path, content_type: str = "") -> None:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        self._s3.upload_file(
            str(ruta_local), self._bucket, key,
            ExtraArgs=extra if extra else None,
        )

    def info_descarga(self, key: str, nombre_archivo: str, content_type: str) -> InfoDescarga:
        url = self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{nombre_archivo}"',
            },
            ExpiresIn=300,
        )
        return InfoDescarga(
            es_url=True,
            valor=url,
            nombre_archivo=nombre_archivo,
            content_type=content_type,
        )

    @contextmanager
    def como_archivo_local(self, key: str, nombre: str) -> Generator[Path, None, None]:
        """Descarga el objeto a un archivo temporal y lo elimina al salir."""
        sufijo = Path(nombre).suffix or ""
        contenido = self.leer(key)
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp:
            tmp.write(contenido)
            tmp_path = Path(tmp.name)
        try:
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)


def crear_storage(
    upload_dir: Path,
    backend: str,
    s3_bucket: str,
    s3_region: str,
) -> IAlmacenamiento:
    """Fábrica: selecciona el backend según la configuración."""
    if backend == "s3" and s3_bucket:
        return S3Storage(bucket=s3_bucket, region=s3_region)
    return LocalStorage(base_dir=upload_dir)
