from unittest.mock import MagicMock

from domain.puertos.repositorios import (
    RepositorioAccesoManual,
    RepositorioDocumento,
    RepositorioExpediente,
    RepositorioFirma,
    RepositorioFormulario,
    RepositorioValidacion,
)
from infrastructure.persistencia.repositorios import (
    RepositorioAccesoManualSQLAlchemy,
    RepositorioDocumentoSQLAlchemy,
    RepositorioExpedienteSQLAlchemy,
    RepositorioFirmaSQLAlchemy,
    RepositorioFormularioSQLAlchemy,
    RepositorioValidacionSQLAlchemy,
)


def test_repositorios_cumplen_protocols():
    """Verifica que cada implementación es reconocida como instancia del Protocol."""
    pares = [
        (RepositorioFormularioSQLAlchemy, RepositorioFormulario),
        (RepositorioDocumentoSQLAlchemy, RepositorioDocumento),
        (RepositorioValidacionSQLAlchemy, RepositorioValidacion),
        (RepositorioExpedienteSQLAlchemy, RepositorioExpediente),
        (RepositorioFirmaSQLAlchemy, RepositorioFirma),
        (RepositorioAccesoManualSQLAlchemy, RepositorioAccesoManual),
    ]

    for impl_cls, protocol_cls in pares:
        instancia = impl_cls(MagicMock())
        assert isinstance(instancia, protocol_cls), (
            f"{impl_cls.__name__} no cumple {protocol_cls.__name__}"
        )
