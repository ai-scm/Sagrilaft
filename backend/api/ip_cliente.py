"""
IP real del cliente detrás del balanceador.

El backend no recibe la conexión del navegador: la recibe del balanceador (ALB
en AWS, nginx en local). El balanceador AGREGA la IP real al final de la
cabecera ``X-Forwarded-For``; lo que haya antes puede haberlo escrito el propio
cliente, así que nunca se usa la primera entrada.

Regla: si la conexión viene de una red de confianza (``TRUSTED_PROXY_IPS``),
se recorre ``X-Forwarded-For`` de derecha a izquierda saltando los proxies de
confianza y se devuelve la primera IP que no lo es. En cualquier otro caso se
devuelve la IP de la conexión y la cabecera se ignora.

``TRUSTED_PROXY_IPS`` admite IP sueltas o rangos CIDR separados por coma (por
ejemplo ``10.0.0.0/16`` o ``172.16.0.0/12,127.0.0.1``). Uvicorn 0.30 no admite
rangos en ``--forwarded-allow-ips``; por eso la regla vive aquí y no en el
servidor.

Es la única fuente de la IP del cliente para el límite de peticiones, el
contador de fallos de autenticación y los registros de seguridad.
"""

import ipaddress
import logging
import os
from functools import lru_cache

from starlette.requests import Request

_log = logging.getLogger(__name__)

_VARIABLE = "TRUSTED_PROXY_IPS"
_POR_DEFECTO = "127.0.0.1"
IP_DESCONOCIDA = "unknown"

Red = ipaddress.IPv4Network | ipaddress.IPv6Network
Direccion = ipaddress.IPv4Address | ipaddress.IPv6Address


def interpretar_redes(valor: str) -> tuple[Red, ...]:
    """Convierte ``"10.0.0.0/16, 127.0.0.1"`` en redes. Falla ante un valor inválido."""
    redes = []
    for parte in valor.split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            redes.append(ipaddress.ip_network(parte, strict=False))
        except ValueError as exc:
            raise ValueError(f"{_VARIABLE} contiene un valor que no es IP ni CIDR: {parte!r}") from exc
    return tuple(redes)


@lru_cache(maxsize=1)
def redes_confiables() -> tuple[Red, ...]:
    """Redes de confianza leídas una vez de ``TRUSTED_PROXY_IPS``."""
    return interpretar_redes(os.getenv(_VARIABLE) or _POR_DEFECTO)


def _direccion(valor: str) -> Direccion | None:
    try:
        return ipaddress.ip_address(valor.strip())
    except ValueError:
        return None


def _es_confiable(direccion: Direccion, redes: tuple[Red, ...]) -> bool:
    return any(direccion in red for red in redes)


def resolver_ip_cliente(
    origen: str | None,
    x_forwarded_for: str | None,
    redes: tuple[Red, ...],
) -> str:
    """Lógica pura, sin ``Request``, para poder probarla caso por caso."""
    if not origen:
        return IP_DESCONOCIDA

    direccion_origen = _direccion(origen)
    if direccion_origen is None or not _es_confiable(direccion_origen, redes):
        return origen
    if not x_forwarded_for:
        return origen

    for entrada in reversed(x_forwarded_for.split(",")):
        direccion = _direccion(entrada)
        if direccion is None:
            # Entrada mal formada: no se puede seguir confiando en lo que hay
            # a su izquierda. Se usa la conexión, que es lo único verificable.
            return origen
        if not _es_confiable(direccion, redes):
            return str(direccion)

    # Toda la cadena es de confianza (llamada interna): la última es la más fiable.
    return origen


def ip_cliente(request: Request) -> str:
    """IP real del cliente de una petición."""
    origen = request.client.host if request.client else None
    return resolver_ip_cliente(origen, request.headers.get("x-forwarded-for"), redes_confiables())
