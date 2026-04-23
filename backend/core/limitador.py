"""
Rate limiter compartido para endpoints sensibles del API SAGRILAFT.

Se instancia una vez a nivel de módulo para que tanto main.py (registro)
como los routers (decoradores) compartan el mismo objeto Limiter.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limitador = Limiter(key_func=get_remote_address)
