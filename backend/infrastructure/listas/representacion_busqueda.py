"""Normalización conservadora de índices, sin recuperación ni clasificación."""
import hashlib
import unicodedata

NORMALIZACION_BUSQUEDA = "nfc-casefold-v1"


def terminos_de(registro):
    for ordinal, nombre in enumerate(registro.nombres):
        valor = unicodedata.normalize("NFC", nombre.valor).casefold()
        yield "NOMBRE", ordinal, hashlib.sha256(valor.encode()).hexdigest()
    for ordinal, identificador in enumerate(registro.identificadores):
        # Documento exacto: sin quitar separadores, ceros, letras o dígitos.
        valor = unicodedata.normalize("NFC", identificador.valor)
        yield "IDENTIFICADOR", ordinal, hashlib.sha256(valor.encode()).hexdigest()
