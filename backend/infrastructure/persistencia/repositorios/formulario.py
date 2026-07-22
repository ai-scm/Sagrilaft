"""Adaptador de persistencia para Formulario — usado por FormularioService."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from domain.formulario.entidades import FormularioDatos
from infrastructure.persistencia.models import AlertaInconsistencia, Formulario

from ._base import RepositorioBase
from ._formulario_helpers import (
    _aplicar_actualizacion_contactos,
    _aplicar_actualizacion_relaciones_uno_a_uno,
    _construir_relaciones_dinamicas,
    _extraer_contactos_para_creacion,
    _extraer_relaciones_uno_a_uno_para_creacion,
    _purgar_datos_no_aplicables_en_payload,
    _purgar_relaciones_no_aplicables,
)
from ._helpers import _normalizar_booleanos_no_nulos
from ._mappers import _orm_formulario_a_datos


class RepositorioFormularioSQLAlchemy(RepositorioBase):
    """Adaptador de persistencia para Formulario — usado por FormularioService."""

    def obtener_por_id(self, formulario_id: str) -> Optional[FormularioDatos]:
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_por_codigo(self, codigo: str) -> Optional[FormularioDatos]:
        """Busca por codigo_peticion o por id. Carga relaciones para snapshot completo."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(
                (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
            )
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def crear(self, datos: Dict[str, Any]) -> FormularioDatos:
        """Persiste un nuevo formulario y retorna su representación de dominio."""
        datos_orm = _extraer_relaciones_uno_a_uno_para_creacion(
            _extraer_contactos_para_creacion(
                _construir_relaciones_dinamicas(
                    _normalizar_booleanos_no_nulos(_purgar_datos_no_aplicables_en_payload(datos))
                )
            )
        )
        orm = Formulario(**datos_orm)
        self._sesion.add(orm)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_formulario_a_datos(orm)

    def actualizar(self, formulario_id: str, campos: Dict[str, Any]) -> FormularioDatos:
        """Actualiza campos específicos y retorna la representación de dominio actualizada."""
        orm = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        if "estado" in campos:
            self._marcar_cambio_auditado()
        campos = _normalizar_booleanos_no_nulos(_purgar_datos_no_aplicables_en_payload(campos, orm))
        relaciones_eliminadas = _purgar_relaciones_no_aplicables(orm, campos)
        for relacion in relaciones_eliminadas:
            self._sesion.delete(relacion)
        _aplicar_actualizacion_contactos(orm, campos)
        campos_relacionales = _aplicar_actualizacion_relaciones_uno_a_uno(orm, campos)
        campos_orm = _extraer_contactos_para_creacion(_construir_relaciones_dinamicas(campos_relacionales))
        campos_orm.pop("contactos", None)
        for clave, valor in campos_orm.items():
            setattr(orm, clave, valor)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_formulario_a_datos(orm)

    def guardar_alertas(self, formulario_id: str, alertas: List[Dict[str, Any]]) -> None:
        """Guarda las alertas de inconsistencia ignoradas por el usuario al enviar."""
        self._sesion.query(AlertaInconsistencia).filter(
            AlertaInconsistencia.formulario_id == formulario_id
        ).delete()

        if alertas:
            orms = [
                AlertaInconsistencia(formulario_id=formulario_id, **alerta)
                for alerta in alertas
            ]
            self._sesion.bulk_save_objects(orms)
        self._sesion.commit()
