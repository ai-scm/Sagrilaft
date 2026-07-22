"""
Implementaciones SQLAlchemy de los puertos de repositorio definidos en domain/puertos/.

Cada clase encapsula las operaciones de base de datos de un servicio específico,
eliminando el acoplamiento directo de los servicios a SQLAlchemy Session.

Todas las instancias de una misma solicitud HTTP comparten la misma Session
(FastAPI cachea Depends(get_db) por request), preservando la atomicidad
transaccional entre servicios.

Estructura del paquete:
    _helpers.py              — funciones genéricas de serialización y normalización
    _formulario_helpers.py   — helpers específicos del formulario (contactos, relaciones)
    _mappers.py              — mapeo ORM → entidades de dominio
    _base.py                 — base compartida para operaciones transversales
    formulario.py            — RepositorioFormularioSQLAlchemy
    documento.py             — RepositorioDocumentoSQLAlchemy
    validacion.py            — RepositorioValidacionSQLAlchemy
    expediente.py            — RepositorioExpedienteSQLAlchemy
    firma.py                 — RepositorioFirmaSQLAlchemy
    acceso_manual.py         — RepositorioAccesoManualSQLAlchemy
"""

from .acceso_manual import RepositorioAccesoManualSQLAlchemy
from .documento import RepositorioDocumentoSQLAlchemy
from .expediente import RepositorioExpedienteSQLAlchemy
from .firma import RepositorioFirmaSQLAlchemy
from .formulario import RepositorioFormularioSQLAlchemy
from .validacion import RepositorioValidacionSQLAlchemy

__all__ = [
    "RepositorioAccesoManualSQLAlchemy",
    "RepositorioDocumentoSQLAlchemy",
    "RepositorioExpedienteSQLAlchemy",
    "RepositorioFirmaSQLAlchemy",
    "RepositorioFormularioSQLAlchemy",
    "RepositorioValidacionSQLAlchemy",
]
