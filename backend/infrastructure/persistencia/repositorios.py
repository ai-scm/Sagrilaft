"""
Implementaciones SQLAlchemy de los puertos de repositorio definidos en domain/puertos/.

Cada clase encapsula las operaciones de base de datos de un servicio específico,
eliminando el acoplamiento directo de los servicios a SQLAlchemy Session.

Todas las instancias de una misma solicitud HTTP comparten la misma Session
(FastAPI cachea Depends(get_db) por request), preservando la atomicidad
transaccional entre servicios.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from domain.constantes import (
    TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
    TIPO_DOCUMENTO_FORMULARIO_PDF,
)
from infrastructure.persistencia.models import (
    AccesoManual,
    DocumentoAdjunto,
    Formulario,
    ResultadoValidacion,
)


class RepositorioFormularioSQLAlchemy:
    """Adaptador de persistencia para Formulario — usado por FormularioService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_por_id(self, formulario_id: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )

    def obtener_por_codigo(self, codigo: str) -> Optional[Formulario]:
        """Busca por codigo_peticion o por id (soporta ambas formas de identificador)."""
        return (
            self._sesion.query(Formulario)
            .filter(
                (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
            )
            .first()
        )

    def agregar(self, formulario: Formulario) -> None:
        self._sesion.add(formulario)

    def confirmar(self) -> None:
        self._sesion.commit()

    def refrescar(self, obj: Any) -> None:
        self._sesion.refresh(obj)


class RepositorioDocumentoSQLAlchemy:
    """Adaptador de persistencia para DocumentoAdjunto — usado por DocumentoService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def buscar(self, formulario_id: str, doc_id: str) -> Optional[DocumentoAdjunto]:
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )

    def listar_activos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .all()
        )

    def agregar(self, documento: DocumentoAdjunto) -> None:
        self._sesion.add(documento)

    def confirmar(self) -> None:
        self._sesion.commit()

    def refrescar(self, obj: Any) -> None:
        self._sesion.refresh(obj)


class RepositorioValidacionSQLAlchemy:
    """Adaptador de persistencia para Formulario + ResultadoValidacion — usado por ValidacionService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )

    def limpiar_validaciones(self, formulario_id: str) -> None:
        self._sesion.query(ResultadoValidacion).filter(
            ResultadoValidacion.formulario_id == formulario_id
        ).delete()

    def agregar_validacion(self, resultado: ResultadoValidacion) -> None:
        self._sesion.add(resultado)

    def confirmar(self) -> None:
        self._sesion.commit()

    def refrescar(self, obj: Any) -> None:
        self._sesion.refresh(obj)


class RepositorioExpedienteSQLAlchemy:
    """Adaptador de persistencia para el portal interno — usado por ExpedienteService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def listar(
        self,
        estados: List[Any],
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
    ) -> List[Formulario]:
        consulta = self._sesion.query(Formulario).filter(
            Formulario.estado.in_(estados)
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
        return consulta.order_by(Formulario.updated_at.desc()).all()

    def obtener(self, formulario_id: str, estados: List[Any]) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(
                Formulario.id == formulario_id,
                Formulario.estado.in_(estados),
            )
            .first()
        )

    def buscar_documento_descargable(
        self, formulario_id: str, doc_id: str, estados: List[Any]
    ) -> Optional[DocumentoAdjunto]:
        return (
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

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.created_at)
            .all()
        )

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

    def confirmar(self) -> None:
        self._sesion.commit()


class RepositorioFirmaSQLAlchemy:
    """Adaptador de persistencia para el flujo de firma — usado por FirmaService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_formulario(self, formulario_id: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )

    def obtener_formulario_por_zoho_id(self, request_id: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.zoho_request_id == request_id)
            .first()
        )

    def obtener_pdf(self, formulario_id: str) -> Optional[DocumentoAdjunto]:
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )

    def obtener_acceso_manual(self, formulario_id: str) -> Optional[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )

    def obtener_certificado(self, formulario_id: str) -> Optional[DocumentoAdjunto]:
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.tipo_documento == TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )

    def agregar_documento(self, documento: DocumentoAdjunto) -> None:
        self._sesion.add(documento)

    def confirmar(self) -> None:
        self._sesion.commit()


class RepositorioAccesoManualSQLAlchemy:
    """Adaptador de persistencia para accesos manuales — usado por AccesoManualService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_acceso_por_token(self, token: str) -> Optional[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(AccesoManual.token_diligenciamiento == token)
            .first()
        )

    def obtener_acceso_por_formulario_id(
        self, formulario_id: str, *, cargar_formulario: bool = False
    ) -> Optional[AccesoManual]:
        consulta = self._sesion.query(AccesoManual).filter(
            AccesoManual.formulario_id == formulario_id
        )
        if cargar_formulario:
            consulta = consulta.options(joinedload(AccesoManual.formulario))
        return consulta.first()

    def obtener_formulario_por_codigo(self, codigo_peticion: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.codigo_peticion == codigo_peticion)
            .first()
        )

    def obtener_acceso_por_formulario(self, formulario: Formulario) -> Optional[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario.id)
            .first()
        )

    def listar_accesos(self) -> List[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .order_by(AccesoManual.created_at.desc())
            .all()
        )

    def agregar_formulario(self, formulario: Formulario) -> None:
        self._sesion.add(formulario)

    def agregar_acceso(self, acceso: AccesoManual) -> None:
        self._sesion.add(acceso)

    def flush(self) -> None:
        self._sesion.flush()

    def confirmar(self) -> None:
        self._sesion.commit()

    def refrescar(self, obj: Any) -> None:
        self._sesion.refresh(obj)
