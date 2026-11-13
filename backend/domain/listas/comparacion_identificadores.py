"""Igualdad por esquema explícito; sin comparación aproximada de números."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class IdentificadorComparable:
    tipo: str
    esquema: str
    valor: str
    digito: str | None
    pais: str | None
    definicion: object
    esquema_explicito: bool


def preparar_identificador(dato, catalogo, fuente=False):
    definicion = catalogo.identificador(dato.tipo)
    if definicion is None or dato.esquema not in (None, definicion.esquema):
        return None
    valor = unicodedata.normalize("NFC", dato.valor)
    if (not any(c.isalnum() for c in valor) or any(marca in valor for marca in ("*", "?", "…", "..."))
            or valor.strip().upper() in {"N/A", "SIN DATO", "DESCONOCIDO", "UNKNOWN", "NO APLICA"}):
        return None
    digito = dato.digito_verificacion
    if digito is not None and not definicion.admite_digito_verificacion:
        return None
    normalizacion = definicion.normalizacion_version
    if normalizacion == "nit-co-v1" and dato.pais_emisor == "CO":
        formato = re.fullmatch(r"([0-9]+(?:\.[0-9]{3})*)(?:-([0-9]))?", valor)
        if formato is None:
            return None
        base, explicito = formato.groups()
        if explicito and digito and explicito != digito:
            return None
        valor, digito = base.replace(".", ""), digito or explicito
    elif normalizacion == "registro-separador-v1":
        if not re.fullmatch(r"[A-Za-z0-9 -]+", valor):
            return None
        valor = valor.replace("-", "").replace(" ", "")
    elif normalizacion == "pasaporte-v1":
        valor = re.sub(r"[\s-]", "", valor)
        if not valor:
            return None
    elif normalizacion not in {"conservacion-v1", "nit-co-v1"}:
        return None
    return IdentificadorComparable(definicion.tipo, definicion.esquema, valor, digito,
        dato.pais_emisor, definicion, not fuente or dato.esquema is not None)


def mismo_esquema(uno, otro):
    return (uno.tipo, uno.esquema) == (otro.tipo, otro.esquema)


def clave_documento(dato):
    return dato.tipo, dato.esquema, dato.pais, dato.valor
