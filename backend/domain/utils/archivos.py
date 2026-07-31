"""
Lectura acotada de archivos subidos por el usuario.

UploadFile.read() sin límite carga el archivo completo a memoria como un solo
bytes object, sin importar cuánta RAM tenga el contenedor. Un archivo gigante
en una sola petición puede agotar la memoria del proceso (DoS de un solo tiro,
sin necesitar volumen de tráfico). Este helper lee en bloques y aborta apenas
se supera el límite, para no retener en memoria más que el límite configurado.
"""

from fastapi import UploadFile

_TAMANO_BLOQUE = 1024 * 1024  # 1 MiB


class ArchivoDemasiadoGrandeError(Exception):
    def __init__(self, max_mb: int):
        self.max_mb = max_mb
        super().__init__(f"El archivo supera el límite permitido de {max_mb} MB.")


async def leer_archivo_limitado(archivo: UploadFile, max_mb: int) -> bytes:
    max_bytes = max_mb * 1024 * 1024
    bloques: list[bytes] = []
    total = 0

    while True:
        bloque = await archivo.read(_TAMANO_BLOQUE)
        if not bloque:
            break
        total += len(bloque)
        if total > max_bytes:
            raise ArchivoDemasiadoGrandeError(max_mb)
        bloques.append(bloque)

    return b"".join(bloques)
