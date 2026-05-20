"""
ExpedienteService — gestión de formularios enviados para el portal interno.

Responsabilidades:
  - Listar formularios en estado no-borrador (enviados, validados, rechazados).
  - Recuperar el detalle completo de un expediente con documentos y validaciones.
  - Resolver la ruta de un documento en disco para descarga directa.
  - Aprobar o rechazar un formulario enviado (cambio de estado manual).
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from domain.constantes import TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT
from domain.excepciones import DocumentoNoEncontradoError, FormularioNoEditableError, FormularioNoEncontradoError
from infrastructure.persistencia.models import (
    DocumentoAdjunto,
    EstadoFormulario,
    Formulario,
)

if TYPE_CHECKING:
    from services.acceso_manual.acceso_manual_service import AccesoManualService
    from services.notificaciones.email_service import EmailService


_ESTADOS_EXPEDIENTE = [
    EstadoFormulario.ENVIADO,
    EstadoFormulario.EN_CORRECCION,
    EstadoFormulario.VALIDADO,
    EstadoFormulario.RECHAZADO,
    EstadoFormulario.PENDIENTE_FIRMA,
    EstadoFormulario.FIRMADO,
]

_ESTADOS_DEVOLVIBLES = {EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO}


class ExpedienteService:
    """
    Servicio de gestión de expedientes para el portal interno.

    Responsabilidades:
      - Listar y detallar formularios en estado no-borrador.
      - Resolver documentos adjuntos para descarga directa.
      - Aprobar o rechazar un formulario enviado (transición de estado manual).
    """

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    # ─── Queries internas ─────────────────────────────────────────────────────

    def _consulta_expedientes(self):
        return self._sesion.query(Formulario).filter(
            Formulario.estado.in_(_ESTADOS_EXPEDIENTE)
        )

    def _buscar_formulario_expediente(self, formulario_id: str) -> Formulario:
        """
        Recupera un formulario únicamente si aplica como expediente.

        Regla: el formulario ya debió haber sido enviado (o estar en estados posteriores
        como validado/rechazado). En borrador, se comporta como "no existe" para el portal.
        """
        formulario = (
            self._sesion.query(Formulario)
            .filter(
                Formulario.id == formulario_id,
                Formulario.estado.in_(_ESTADOS_EXPEDIENTE),
            )
            .first()
        )
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _buscar_documento_descargable(
        self, formulario_id: str, doc_id: str
    ) -> DocumentoAdjunto | None:
        """
        Retorna el documento si y solo si pertenece a un expediente (no borrador).

        Regla de negocio: para descargar desde el portal interno, el formulario
        ya debió haber sido enviado (o estar en estados posteriores como validado/rechazado).
        """
        return (
            self._sesion.query(DocumentoAdjunto)
            .join(Formulario, Formulario.id == DocumentoAdjunto.formulario_id)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
                Formulario.estado.in_(_ESTADOS_EXPEDIENTE),
            )
            .first()
        )

    def _conteos_documentos_por_formulario(self, ids_formularios: list[str]) -> dict[str, int]:
        """Cuenta documentos activos en una sola query GROUP BY — evita N+1.

        Excluye el certificado SAGRILAFT porque es un artefacto de firma generado
        automáticamente, no un documento subido por el usuario. El contador debe
        coincidir con lo que el operador ve en el detalle del expediente.
        """
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

    # ─── Serialización ────────────────────────────────────────────────────────

    def _serializar_resumen(self, formulario: Formulario, cantidad_documentos: int) -> Dict[str, Any]:
        return {
            "formulario_id":         formulario.id,
            "codigo_peticion":       formulario.codigo_peticion,
            "razon_social":          formulario.razon_social,
            "numero_identificacion": formulario.numero_identificacion,
            "tipo_contraparte":      formulario.tipo_contraparte,
            "tipo_persona":          formulario.tipo_persona,
            "estado":                formulario.estado,
            "cantidad_documentos":   cantidad_documentos,
            "created_at":            formulario.created_at,
            "updated_at":            formulario.updated_at,
        }

    # ─── Listado ──────────────────────────────────────────────────────────────

    def listar_expedientes(
        self,
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retorna todos los formularios no-borrador ordenados por fecha de actualización.

        Acepta filtros opcionales: tipo_contraparte ('cliente'/'proveedor') y búsqueda
        de texto libre en razón social y código de petición (case-insensitive).
        """
        consulta = self._consulta_expedientes()

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

        formularios = consulta.order_by(Formulario.updated_at.desc()).all()
        conteos     = self._conteos_documentos_por_formulario([f.id for f in formularios])
        return [self._serializar_resumen(f, conteos.get(f.id, 0)) for f in formularios]

    # ─── Detalle ──────────────────────────────────────────────────────────────

    def obtener_expediente(self, formulario_id: str) -> Dict[str, Any]:
        """
        Recupera los metadatos del expediente y sus documentos adjuntos.

        Devuelve únicamente los campos que el portal necesita para la vista de detalle.
        Los datos del formulario (financieros, tributarios, etc.) no se exponen aquí —
        están disponibles exclusivamente en el PDF descargable.

        Lanza FormularioNoEncontradoError si el formulario no existe o está en borrador.
        """
        formulario = self._buscar_formulario_expediente(formulario_id)

        documentos = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.created_at)
            .all()
        )

        return {
            "formulario_id":    formulario.id,
            "codigo_peticion":  formulario.codigo_peticion,
            "razon_social":     formulario.razon_social,
            "tipo_contraparte": formulario.tipo_contraparte,
            "estado":           formulario.estado,
            "updated_at":       formulario.updated_at,
            "documentos": [
                {
                    "id":             doc.id,
                    "tipo_documento": doc.tipo_documento,
                    "nombre_archivo": doc.nombre_archivo,
                    "tamano":         doc.tamano,
                }
                for doc in documentos
            ],
        }

    # ─── Aprobación / Rechazo ─────────────────────────────────────────────────

    def aprobar_expediente(self, formulario_id: str) -> Dict[str, Any]:
        """Cambia el estado de ENVIADO a VALIDADO (aprobación manual del portal interno)."""
        formulario = self._buscar_formulario_expediente(formulario_id)
        if formulario.estado != EstadoFormulario.ENVIADO:
            raise FormularioNoEditableError(
                f"Solo se puede aprobar un formulario en estado 'enviado' (actual: '{formulario.estado}')."
            )
        formulario.estado = EstadoFormulario.VALIDADO
        self._sesion.commit()
        return {"estado": formulario.estado}

    def rechazar_expediente(self, formulario_id: str) -> Dict[str, Any]:
        """Cambia el estado de ENVIADO o VALIDADO a RECHAZADO."""
        formulario = self._buscar_formulario_expediente(formulario_id)
        if formulario.estado not in (EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO):
            raise FormularioNoEditableError(
                f"Solo se puede rechazar un formulario en estado 'enviado' o 'validado' (actual: '{formulario.estado}')."
            )
        formulario.estado = EstadoFormulario.RECHAZADO
        self._sesion.commit()
        return {"estado": formulario.estado}

    def devolver_para_correccion(
        self,
        formulario_id: str,
        especificaciones: str,
        campos_identificados: List[str],
        acceso_service: "AccesoManualService",
        email_service: Optional["EmailService"] = None,
    ) -> Dict[str, Any]:
        """
        Devuelve el formulario al remitente para que corrija la información indicada.

        Transiciones permitidas: ENVIADO → EN_CORRECCION, VALIDADO → EN_CORRECCION.
        Reactiva el acceso manual vinculado y notifica al destinatario por correo.

        Los campos_identificados se persisten como JSON junto con las especificaciones,
        permitiendo que el formulario destaque visualmente los campos que requieren atención.
        """
        formulario = self._buscar_formulario_expediente(formulario_id)

        estado_actual = formulario.estado
        if isinstance(estado_actual, str):
            estado_actual = EstadoFormulario(estado_actual)

        if estado_actual not in _ESTADOS_DEVOLVIBLES:
            raise FormularioNoEditableError(
                f"Solo se puede devolver un formulario en estado 'enviado' o 'validado' "
                f"(actual: '{formulario.estado}')."
            )

        formulario.estado            = EstadoFormulario.EN_CORRECCION
        formulario.campos_a_corregir = json.dumps(
            {"especificaciones": especificaciones, "campos": campos_identificados},
            ensure_ascii=False,
        )

        datos_acceso = acceso_service.reactivar_acceso_para_correccion(formulario_id)
        self._sesion.commit()

        correo_notificado = datos_acceso["correo_destinatario"] if datos_acceso else None
        enlace_acceso     = datos_acceso["enlace_diligenciamiento"] if datos_acceso else None

        correo_enviado = False
        if email_service and correo_notificado:
            correo_enviado = email_service.enviar_notificacion_devolucion(
                correo_destinatario=correo_notificado,
                especificaciones_correccion=especificaciones,
                enlace_diligenciamiento=enlace_acceso,
                campos_identificados=campos_identificados or None,
            )

        return {
            "estado":            formulario.estado,
            "correo_notificado": correo_notificado,
            "correo_enviado":    correo_enviado,
        }

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def resolver_documento_para_descarga(
        self, formulario_id: str, doc_id: str
    ) -> tuple[Path, str, str]:
        """
        Verifica que el documento pertenece al expediente y devuelve su ruta en disco.

        Returns:
            (ruta_archivo, nombre_archivo, content_type)

        Lanza DocumentoNoEncontradoError si el documento no existe, fue eliminado
        o el archivo ya no está en disco.
        """
        documento = self._buscar_documento_descargable(formulario_id, doc_id)
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)

        ruta = Path(documento.ruta_archivo)
        if not ruta.exists():
            raise DocumentoNoEncontradoError(formulario_id, doc_id)

        content_type = documento.content_type or "application/octet-stream"
        return ruta, documento.nombre_archivo, content_type
