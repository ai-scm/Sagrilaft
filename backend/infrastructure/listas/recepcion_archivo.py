"""Escritura limitada del original. No descomprime ni interpreta XML."""
import hashlib
import os
import tempfile
import stat
from infrastructure.listas.custodia import ObjetoCustodiado
from domain.listas.errores import ErrorIntegridadEvidencia


class LimiteCarga(ValueError):
    pass


class ArchivoEnRecepcion:
    def __init__(self, custodia, limite):
        self.custodia, self.limite = custodia, limite
        descriptor, self.temporal = tempfile.mkstemp(prefix='recepcion-', dir=custodia.directorio)
        self.archivo = os.fdopen(descriptor, 'wb')
        self.huella, self.tamano = hashlib.sha256(), 0

    def escribir(self, bloque):
        if self.tamano + len(bloque) > self.limite:
            raise LimiteCarga('El archivo excede el límite de recepción')
        self.archivo.write(bloque)
        self.huella.update(bloque)
        self.tamano += len(bloque)

    def confirmar(self, esperada):
        huella = self.huella.hexdigest()
        if not self.tamano or huella != esperada:
            raise ErrorIntegridadEvidencia('Hash o tamaño del original no válido')
        self.archivo.flush()
        os.fsync(self.archivo.fileno())
        self.archivo.close()
        destino = self.custodia.directorio / huella
        try:
            os.link(self.temporal, destino)
        except FileExistsError:
            with original_verificado(self.custodia, huella, self.tamano):
                pass
        descriptor = os.open(self.custodia.directorio, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return ObjetoCustodiado(huella, huella, self.tamano)

    def cerrar(self):
        self.archivo.close()
        try:
            os.unlink(self.temporal)
        except FileNotFoundError:
            pass


def original_verificado(custodia, huella, tamano):
    """Devuelve copia temporal verificada antes de entregar un solo byte al cliente."""
    import re
    if not re.fullmatch(r'[a-f0-9]{64}', huella):
        raise ErrorIntegridadEvidencia('Clave inválida')
    copia = tempfile.TemporaryFile(dir=custodia.directorio)
    try:
        descriptor = os.open(custodia.directorio / huella, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ErrorIntegridadEvidencia("El original no es un archivo regular")
        calculada, total = hashlib.sha256(), 0
        with os.fdopen(descriptor, 'rb') as archivo:
            while bloque := archivo.read(65536):
                total += len(bloque)
                if total > tamano:
                    raise ErrorIntegridadEvidencia('Tamaño alterado')
                calculada.update(bloque)
                copia.write(bloque)
        if total != tamano or calculada.hexdigest() != huella:
            raise ErrorIntegridadEvidencia('Original alterado')
        copia.seek(0)
        return copia
    except BaseException:
        copia.close()
        raise
