"""Adaptador de persistencia para el flujo de firma — usado por FirmaService."""

from typing import Any, Dict, Optional

from domain.constantes import (
    TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
)
from domain.contratos import AccesoManualDatos, DocumentoDatos
from domain.formulario.entidades import FormularioDatos
from infrastructure.persistencia.models import AccesoManual, DocumentoAdjunto, Formulario

from ._base import RepositorioBase
from ._mappers import _orm_acceso_manual_a_datos, _orm_documento_a_datos, _orm_formulario_a_datos


class RepositorioFirmaSQLAlchemy(RepositorioBase):
    """Adaptador de persistencia para el flujo de firma — usado por FirmaService."""

    def obtener_formulario(self, formulario_id: str, bloquear: bool = False) -> Optional[FormularioDatos]:
        orm = self._obtener_formulario_orm(formulario_id, bloquear=bloquear)
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_formulario_por_zoho_id(self, request_id: str, bloquear: bool = False) -> Optional[FormularioDatos]:
        consulta = (
            self._sesion.query(Formulario)
            .filter(Formulario.zoho_request_id == request_id)
        )
        if bloquear:
            consulta = consulta.with_for_update()
        orm = consulta.first()
        return _orm_formulario_a_datos(orm) if orm else None

    def obtener_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]:
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

    def obtener_acceso_manual(self, formulario_id: str) -> Optional[AccesoManualDatos]:
        orm = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )
        return _orm_acceso_manual_a_datos(orm) if orm else None

    def obtener_certificado(self, formulario_id: str) -> Optional[DocumentoDatos]:
        orm = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        return _orm_documento_a_datos(orm) if orm else None

    def crear_documento(self, datos: Dict[str, Any]) -> None:
        self._sesion.add(DocumentoAdjunto(**datos))
        self._sesion.commit()

    def actualizar_formulario(self, formulario_id: str, campos: Dict[str, Any]) -> None:
        orm = self._sesion.query(Formulario).filter(Formulario.id == formulario_id).first()
        if orm:
            if "estado" in campos:
                self._marcar_cambio_auditado()
            for campo, valor in campos.items():
                setattr(orm, campo, valor)
            self._sesion.commit()

    def actualizar_certificado(self, doc_id: str, ruta_archivo: str, tamano: int, hash_sha256: str) -> None:
        orm = self._sesion.query(DocumentoAdjunto).filter(DocumentoAdjunto.id == doc_id).first()
        if orm:
            orm.ruta_archivo = ruta_archivo
            orm.tamano = tamano
            orm.hash_sha256 = hash_sha256
            self._sesion.commit()
