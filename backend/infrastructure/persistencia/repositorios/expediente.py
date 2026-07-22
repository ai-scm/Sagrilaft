"""Adaptador de persistencia para el portal interno — usado por ExpedienteService."""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_

from domain.constantes import TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT
from domain.contratos import DocumentoDatos
from domain.formulario.entidades import FormularioDatos
from infrastructure.persistencia.models import (
    AlertaInconsistencia,
    DocumentoAdjunto,
    Formulario,
)

from ._base import RepositorioBase
from ._mappers import _orm_documento_a_datos, _orm_formulario_a_datos


class RepositorioExpedienteSQLAlchemy(RepositorioBase):
    """Adaptador de persistencia para el portal interno — usado por ExpedienteService."""

    def listar(
        self,
        estados: List[Any],
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> List[FormularioDatos]:
        consulta = self._sesion.query(Formulario).filter(
            Formulario.estado.in_(estados)
        )
        if contrapartes_permitidas is not None:
            consulta = consulta.filter(
                Formulario.tipo_contraparte.in_(contrapartes_permitidas)
            )
        if tipo_contraparte:
            consulta = consulta.filter(
                Formulario.tipo_contraparte == tipo_contraparte.lower()
            )
        if busqueda:
            termino = f"%{busqueda.strip()}%"
            consulta = consulta.filter(
                or_(
                    Formulario.razon_social.ilike(termino),
                    Formulario.codigo_peticion.ilike(termino),
                )
            )
        orms = consulta.order_by(Formulario.updated_at.desc()).all()
        return [_orm_formulario_a_datos(orm) for orm in orms]

    def obtener(self, formulario_id: str, estados: List[Any], bloquear: bool = False) -> Optional[FormularioDatos]:
        consulta = (
            self._sesion.query(Formulario)
            .filter(
                Formulario.id == formulario_id,
                Formulario.estado.in_(estados),
            )
        )
        if bloquear:
            consulta = consulta.with_for_update()
        orm = consulta.first()
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def buscar_documento_descargable(
        self, formulario_id: str, doc_id: str, estados: List[Any]
    ) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .join(Formulario, Formulario.id == DocumentoAdjunto.formulario_id)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
                Formulario.estado.in_(estados),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def listar_documentos(self, formulario_id: str) -> List[DocumentoDatos]:
        orms = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.created_at)
            .all()
        )
        return [_orm_documento_a_datos(orm) for orm in orms]

    def contar_documentos(self, ids_formularios: List[str]) -> Dict[str, int]:
        filas = (
            self._sesion.query(
                DocumentoAdjunto.formulario_id,
                func.count(DocumentoAdjunto.id).label("total"),
            )
            .filter(
                DocumentoAdjunto.formulario_id.in_(ids_formularios),
                DocumentoAdjunto.deleted_at.is_(None),
                DocumentoAdjunto.tipo_documento != TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
            )
            .group_by(DocumentoAdjunto.formulario_id)
            .all()
        )
        return {fila.formulario_id: fila.total for fila in filas}

    def actualizar_estado(self, formulario_id: str, estado: str) -> None:
        """Marca el nuevo estado en la sesión sin hacer commit.

        El commit lo realiza el caller (handler) después de registrar
        el evento de auditoría, garantizando que ambas operaciones sean
        atómicas en la misma transacción.
        """
        self._actualizar_campos_formulario(
            formulario_id,
            {"estado": estado},
            hacer_commit=False,
        )

    def actualizar_sagrilaft_reporte_id(self, formulario_id: str, reporte_id: str) -> None:
        """Persiste el ID del reporte de SAGRILAFT para descargas posteriores."""
        if reporte_id:
            self._actualizar_campos_formulario(
                formulario_id,
                {"sagrilaft_reporte_id": reporte_id},
            )

    def _actualizar_campos_formulario(
        self,
        formulario_id: str,
        campos: Dict[str, Any],
        *,
        hacer_commit: bool = True,
    ) -> None:
        """Aplica campos arbitrarios a un formulario con marca de auditoría."""
        orm = self._obtener_formulario_orm(formulario_id)
        if orm:
            self._marcar_cambio_auditado()
            for campo, valor in campos.items():
                setattr(orm, campo, valor)
            if hacer_commit:
                self._sesion.commit()

    def actualizar_para_correccion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
        campos_a_corregir: str,
    ) -> None:
        """
        Persiste los campos de una devolución para corrección y hace commit.

        El commit de este método también confirma los cambios de AccesoManual
        pendientes en la misma sesión (AccesoManualService.reactivar_acceso_para_correccion
        modifica la sesión sin hacer commit, delegando aquí esa responsabilidad).
        """
        self._actualizar_campos_formulario(
            formulario_id,
            {
                "estado": estado,
                "numero_correccion": numero_correccion,
                "campos_a_corregir": campos_a_corregir,
            },
        )

    def actualizar_para_deshacer_devolucion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
    ) -> None:
        """
        Revierte los campos de una devolución para corrección y hace commit.
        """
        self._actualizar_campos_formulario(
            formulario_id,
            {
                "estado": estado,
                "numero_correccion": numero_correccion,
                "campos_a_corregir": None,
            },
        )

    def actualizar_para_reapertura_actualizacion(
        self,
        formulario_id: str,
        estado: str,
        campos_a_corregir: str,
    ) -> None:
        """
        Persiste la reapertura de una actualización y hace commit.

        El commit confirma también la reactivación del AccesoManual pendiente
        en la misma sesión.
        """
        self._actualizar_campos_formulario(
            formulario_id,
            {
                "estado": estado,
                "campos_a_corregir": campos_a_corregir,
            },
        )

    def actualizar_estado_alerta(
        self,
        formulario_id: str,
        alerta_id: str,
        estado_auditoria: str,
        actor_id: str,
    ) -> None:
        self._sesion.query(AlertaInconsistencia).filter(
            AlertaInconsistencia.id == alerta_id,
            AlertaInconsistencia.formulario_id == formulario_id
        ).update({
            "estado_auditoria": estado_auditoria,
            "actualizado_por": actor_id,
        })
        self._sesion.commit()
