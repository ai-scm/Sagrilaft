"""Base compartida para repositorios SQLAlchemy."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class RepositorioBase:
    """
    Convención de transacciones:
    - Los métodos que documentan "sin commit" modifican la sesión sin confirmar.
    - Todos los demás métodos hacen commit al finalizar.
    - El caller es responsable de manejar excepciones y rollback.
    """

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def _marcar_cambio_auditado(self) -> None:
        """Informa al trigger de auditoría que el cambio viene de la aplicación."""
        self._sesion.execute(text("SET LOCAL sagrilaft.from_app = '1'"))

    def _obtener_formulario_orm(self, formulario_id: str, *, bloquear: bool = False) -> Any:
        """Query reutilizable para obtener un Formulario por ID."""
        from infrastructure.persistencia.models import Formulario

        consulta = self._sesion.query(Formulario).filter(Formulario.id == formulario_id)
        if bloquear:
            consulta = consulta.with_for_update()
        return consulta.first()
