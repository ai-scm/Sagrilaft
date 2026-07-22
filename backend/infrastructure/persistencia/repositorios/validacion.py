"""Adaptador de persistencia para Formulario + ResultadoValidacion — usado por ValidacionService."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from domain.formulario.entidades import FormularioDatos
from domain.validacion.resultado import ResultadoValidacionDominio
from infrastructure.persistencia.models import Formulario, ResultadoValidacion

from ._mappers import _orm_formulario_a_datos, _orm_validacion_a_dominio


class RepositorioValidacionSQLAlchemy:
    """Adaptador de persistencia para Formulario + ResultadoValidacion — usado por ValidacionService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .options(joinedload(Formulario.documentos))
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def limpiar_validaciones(self, formulario_id: str) -> None:
        self._sesion.query(ResultadoValidacion).filter(
            ResultadoValidacion.formulario_id == formulario_id
        ).delete()

    def guardar_validaciones(self, datos: List[Dict[str, Any]]) -> List[ResultadoValidacionDominio]:
        """Inserta todos los resultados de validación en una transacción y devuelve entidades de dominio."""
        orms = [ResultadoValidacion(**d) for d in datos]
        for orm in orms:
            self._sesion.add(orm)
        self._sesion.commit()
        for orm in orms:
            self._sesion.refresh(orm)
        return [_orm_validacion_a_dominio(orm) for orm in orms]
