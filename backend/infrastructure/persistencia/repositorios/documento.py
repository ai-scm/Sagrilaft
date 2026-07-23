"""Adaptador de persistencia para DocumentoAdjunto — usado por DocumentoService."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.contratos import DocumentoDatos
from infrastructure.persistencia.models import DocumentoAdjunto

from ._helpers import _aplicar_serializacion
from ._mappers import _orm_documento_a_datos


class RepositorioDocumentoSQLAlchemy:
    """Adaptador de persistencia para DocumentoAdjunto — usado por DocumentoService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def buscar(self, formulario_id: str, doc_id: str) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def obtener_activo_por_tipo_con_bloqueo(
        self, formulario_id: str, tipo_documento: str
    ) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == tipo_documento,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def listar_activos(self, formulario_id: str) -> List[DocumentoDatos]:
        orms = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .all()
        )
        return [_orm_documento_a_datos(o) for o in orms]

    def crear(self, datos: Dict[str, Any]) -> DocumentoDatos:
        """Persiste un nuevo documento adjunto y retorna su representación de dominio."""
        orm = DocumentoAdjunto(**_aplicar_serializacion(datos))
        self._sesion.add(orm)
        self._sesion.commit()
        self._sesion.refresh(orm)
        return _orm_documento_a_datos(orm)

    def actualizar_rutas(self, rutas: Dict[str, str]) -> None:
        """Actualiza las rutas de archivo de varios documentos en una sola transacción."""
        for doc_id, nueva_ruta in rutas.items():
            self._sesion.query(DocumentoAdjunto).filter(
                DocumentoAdjunto.id == doc_id
            ).update({"ruta_archivo": nueva_ruta})
        self._sesion.commit()

    def marcar_eliminado(self, doc_id: str) -> None:
        """Soft-delete: registra la fecha de eliminación del documento."""
        self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id
        ).update({"deleted_at": datetime.now(timezone.utc)})
        self._sesion.commit()

    def actualizar_snapshot_datos(self, doc_id: str, snapshot_datos: str) -> None:
        """Actualiza la columna snapshot_datos de un documento específico."""
        self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id
        ).update({"snapshot_datos": snapshot_datos})
        self._sesion.commit()

    def obtener_ultimo_formulario_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]:
        """
        Retorna el PDF del formulario con el mayor version_numero activo.

        Se usa como ancla para construir la cadena de versiones al generar
        un nuevo PDF: el nuevo documento apuntará a este como version_anterior_id.
        """
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.version_numero.desc())
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None
