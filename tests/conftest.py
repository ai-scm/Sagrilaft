"""
Configuracion compartida de pruebas.

Mantiene el backend importable sin depender del directorio desde donde se
ejecute pytest ni de la profundidad de cada archivo de prueba.
"""

import os
import sys
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
BACKEND_DIR = RAIZ_PROYECTO / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def configurar_entorno_base_pruebas() -> None:
    """Define mínimos seguros para importar módulos del backend en pruebas."""

    valores = {
        "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/db",
        "SECRET_KEY": "test-secret",
        "APP_ENV": "development",
        "PORTAL_INTERNO_URL": "https://portal.test",
    }
    for nombre, valor in valores.items():
        os.environ.setdefault(nombre, valor)


configurar_entorno_base_pruebas()
