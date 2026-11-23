"""
Rate limiter compartido para endpoints sensibles del API SAGRILAFT.

Se instancia una vez a nivel de módulo para que tanto main.py (registro)
como los routers (decoradores) compartan el mismo objeto Limiter.

La clave es la IP real del cliente (ver api/ip_cliente.py), no la del
balanceador: así cada contraparte tiene su propio cupo.
"""

from slowapi import Limiter

from api.ip_cliente import ip_cliente

limitador = Limiter(key_func=ip_cliente)
