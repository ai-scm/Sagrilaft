"""
ExpedienteService — gestión de formularios enviados para el portal interno.

Responsabilidades:
  - Listar formularios en estado no-borrador (enviados, validados, rechazados).
  - Recuperar el detalle completo de un expediente con documentos y validaciones.
  - Resolver la ruta de un documento en disco para descarga directa.
  - Aprobar o rechazar un formulario enviado (cambio de estado manual).
"""

import json
from datetime import datetime, timezone
from html import escape
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.excepciones import (
    DocumentoNoEncontradoError,
    FormularioNoEncontradoError,
    SinPermisoError,
)
from domain.formulario.entidades import FormularioDominio
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.notificaciones import INotificador
from domain.puertos.repositorios import RepositorioExpediente, RepositorioDocumento
from domain.formulario.tipos import EstadoFormulario
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from services.expedientes.comparacion_versiones import (
    comparar_versiones,
    comparacion_versiones_a_dict,
)

if TYPE_CHECKING:
    from services.acceso_manual.acceso_manual_service import AccesoManualService  # noqa: F401


_ESTADOS_EXPEDIENTE = [
    EstadoFormulario.ENVIADO,
    EstadoFormulario.EN_CORRECCION,
    EstadoFormulario.VALIDADO,
    EstadoFormulario.RECHAZADO,
    EstadoFormulario.PENDIENTE_FIRMA,
    EstadoFormulario.FIRMADO,
    EstadoFormulario.CERRADO,
]


class ExpedienteService:
    """
    Servicio de gestión de expedientes para el portal interno.

    Responsabilidades:
      - Listar y detallar formularios en estado no-borrador.
      - Resolver documentos adjuntos para descarga directa.
      - Aprobar o rechazar un formulario enviado (transición de estado manual).
    """

    def __init__(
        self,
        repo: RepositorioExpediente,
        repo_doc: RepositorioDocumento,
        storage: IAlmacenamiento,
        repo_auditoria: Optional[RepositorioAuditoria] = None,
        alertas_portal: Optional[IAlertasPortal] = None,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._auditoria = repo_auditoria
        self._alertas = alertas_portal
        from services.formulario.documento_service import DocumentoService
        self._documentos = DocumentoService(repo_doc, storage)

    # ─── Helpers internos ─────────────────────────────────────────────────────

    def _registrar(self, evento: EventoAuditoria) -> None:
        """Registra un evento de auditoría si el repositorio está disponible."""
        if self._auditoria:
            self._auditoria.registrar_evento(evento)

    def _alertar(self, tipo: TipoAlerta, formulario, detalle: Optional[str] = None) -> None:
        """Dispara una alerta al portal si el adaptador está disponible."""
        if self._alertas:
            self._alertas.alertar(
                tipo=tipo,
                formulario_id=formulario.id,
                razon_social=formulario.razon_social or "",
                tipo_contraparte=formulario.tipo_contraparte or "",
                codigo_peticion=formulario.codigo_peticion,
                detalle=detalle,
            )

    def _buscar_formulario_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ):
        formulario = self._repo.obtener(formulario_id, _ESTADOS_EXPEDIENTE)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)
        return formulario

    def _buscar_documento_descargable(self, formulario_id: str, doc_id: str):
        return self._repo.buscar_documento_descargable(
            formulario_id, doc_id, _ESTADOS_EXPEDIENTE
        )

    def _conteos_documentos_por_formulario(self, ids_formularios: list[str]) -> dict[str, int]:
        return self._repo.contar_documentos(ids_formularios)

    def _serializar_resumen(self, formulario, cantidad_documentos: int) -> Dict[str, Any]:
        return {
            "formulario_id":         formulario.id,
            "codigo_peticion":       formulario.codigo_peticion,
            "razon_social":          formulario.razon_social,
            "numero_identificacion": formulario.numero_identificacion,
            "tipo_contraparte":      formulario.tipo_contraparte,
            "tipo_persona":          formulario.tipo_persona,
            "estado":                formulario.estado,
            "numero_correccion":     formulario.numero_correccion or 0,
            "cantidad_documentos":   cantidad_documentos,
            "created_at":            formulario.created_at,
            "updated_at":            formulario.updated_at,
        }

    # ─── Listado ──────────────────────────────────────────────────────────────

    def listar_expedientes(
        self,
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        formularios = self._repo.listar(
            _ESTADOS_EXPEDIENTE, tipo_contraparte, busqueda, contrapartes_permitidas
        )
        conteos = self._conteos_documentos_por_formulario([f.id for f in formularios])
        return [self._serializar_resumen(f, conteos.get(f.id, 0)) for f in formularios]

    # ─── Detalle ──────────────────────────────────────────────────────────────

    def obtener_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documentos = self._repo.listar_documentos(formulario_id)
        return {
            "formulario_id":     formulario.id,
            "codigo_peticion":   formulario.codigo_peticion,
            "razon_social":      formulario.razon_social,
            "tipo_contraparte":  formulario.tipo_contraparte,
            "tipo_persona":      formulario.tipo_persona,
            "estado":            formulario.estado,
            "numero_correccion": formulario.numero_correccion or 0,
            "updated_at":        formulario.updated_at,
            "documentos": [
                {
                    "id":             doc.id,
                    "tipo_documento": doc.tipo_documento,
                    "nombre_archivo": doc.nombre_archivo,
                    "tamano":         doc.tamano,
                    "version_numero": doc.version_numero,
                    "version_anterior_id": doc.version_anterior_id,
                    "created_at":     doc.created_at,
                    "subido_por":     doc.subido_por,
                }
                for doc in documentos
            ],
        }

    def comparar_ultima_correccion(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documento_corregido = self._documentos.obtener_ultimo_formulario_pdf(formulario_id)
        if not documento_corregido:
            raise DocumentoNoEncontradoError(formulario_id, TIPO_DOCUMENTO_FORMULARIO_PDF)

        documento_anterior = None
        if documento_corregido.version_anterior_id:
            documento_anterior = self._documentos.buscar_documento(
                formulario_id,
                documento_corregido.version_anterior_id,
            )

        comparacion = comparar_versiones(documento_corregido, documento_anterior)
        return comparacion_versiones_a_dict(comparacion)

    def generar_reporte_comparacion_pdf(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> bytes:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        comparacion = self.comparar_ultima_correccion(formulario_id, contrapartes_permitidas)
        html = _html_reporte_comparacion(formulario, comparacion)

        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RuntimeError("No se encontró 'weasyprint' para generar el PDF de comparación.") from exc

        return HTML(string=html).write_pdf()

    # ─── Carga Manual ─────────────────────────────────────────────────────────

    def cargar_formulario_manual(
        self,
        formulario_id: str,
        archivo_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
        justificacion: str,
        actor_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if content_type != "application/pdf":
            raise ValueError("Solo se permite formato PDF.")
        if len(justificacion.strip()) < 20:
            raise ValueError("La justificación debe tener al menos 20 caracteres.")

        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado

        from services.formulario.almacenamiento_contraparte import resolver_key_contraparte
        from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF

        prefijo = resolver_key_contraparte(formulario.tipo_contraparte, formulario.razon_social)
        pdf_anterior = self._documentos.obtener_ultimo_formulario_pdf(formulario_id)
        numero_version_nuevo = (pdf_anterior.version_numero + 1) if pdf_anterior else 1

        key_pdf = f"{prefijo}/{nombre_archivo}"
        self._documentos.guardar_archivo(key_pdf, archivo_bytes, content_type)
        self._documentos.registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=TIPO_DOCUMENTO_FORMULARIO_PDF,
            nombre_archivo=nombre_archivo,
            key=key_pdf,
            content_type=content_type,
            tamano=len(archivo_bytes),
            hash_sha256=self._documentos.calcular_hash(archivo_bytes),
            subido_por=actor_id,
            version_numero=numero_version_nuevo,
            version_anterior_id=pdf_anterior.id if pdf_anterior else None,
        )

        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.carga_manual()
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)

        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_CARGADO_MANUALMENTE,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={"upload_method": "MANUAL", "upload_reason": justificacion.strip()},
        ))

        self._alertar(TipoAlerta.FORMULARIO_RECIBIDO, formulario, detalle="Carga manual de formulario")

        return {"estado": dominio.estado.value, "version_numero": numero_version_nuevo}

    def cargar_reporte_final(
        self,
        formulario_id: str,
        archivo_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
        justificacion: str,
        actor_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if content_type != "application/pdf":
            raise ValueError("Solo se permite formato PDF para el reporte final.")

        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado

        from services.formulario.almacenamiento_contraparte import resolver_key_contraparte
        from domain.constantes import TIPO_DOCUMENTO_REPORTE_FINAL

        reportes_previos = [d for d in self._documentos.listar_documentos(formulario_id) if d.tipo_documento == TIPO_DOCUMENTO_REPORTE_FINAL]
        if reportes_previos:
            reporte_anterior = max(reportes_previos, key=lambda d: d.version_numero)
            numero_version_nuevo = reporte_anterior.version_numero + 1
            version_anterior_id = reporte_anterior.id
        else:
            numero_version_nuevo = 1
            version_anterior_id = None

        prefijo = resolver_key_contraparte(formulario.tipo_contraparte, formulario.razon_social)
        key_pdf = f"{prefijo}/reportes_finales/{nombre_archivo}"
        self._documentos.guardar_archivo(key_pdf, archivo_bytes, content_type)
        self._documentos.registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=TIPO_DOCUMENTO_REPORTE_FINAL,
            nombre_archivo=nombre_archivo,
            key=key_pdf,
            content_type=content_type,
            tamano=len(archivo_bytes),
            hash_sha256=self._documentos.calcular_hash(archivo_bytes),
            subido_por=actor_id,
            version_numero=numero_version_nuevo,
            version_anterior_id=version_anterior_id,
        )

        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.cerrar_con_reporte()
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)

        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.REPORTE_FINAL_CARGADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={"justificacion": justificacion.strip(), "version": numero_version_nuevo},
        ))

        return {"estado": dominio.estado.value, "version_numero": numero_version_nuevo}

    # ─── Aprobación / Rechazo ─────────────────────────────────────────────────

    def aprobar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.aprobar()
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_APROBADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
        ))
        return {"estado": dominio.estado.value}

    def rechazar_expediente(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
        motivo: str = "",
        mensaje_para_destinatario: Optional[str] = None,
        acceso_service: Optional["AccesoManualService"] = None,
        email_service: Optional[INotificador] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.rechazar()
        self._repo.actualizar_estado(formulario_id, dominio.estado.value)
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_RECHAZADO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={"motivo": motivo},
        ))
        notificacion_enviada = self._notificar_rechazo_si_aplica(
            formulario_id=formulario_id,
            mensaje_para_destinatario=mensaje_para_destinatario,
            acceso_service=acceso_service,
            email_service=email_service,
        )
        return {
            "estado":               dominio.estado.value,
            "motivo":               motivo,
            "notificacion_enviada": notificacion_enviada,
        }

    def _notificar_rechazo_si_aplica(
        self,
        formulario_id: str,
        mensaje_para_destinatario: Optional[str],
        acceso_service: Optional["AccesoManualService"],
        email_service: Optional[INotificador],
    ) -> bool:
        if not mensaje_para_destinatario:
            return False
        if not acceso_service or not email_service:
            return False
        correo_destinatario = acceso_service.obtener_correo_destinatario(formulario_id)
        if not correo_destinatario:
            return False
        return email_service.enviar_notificacion_rechazo(
            correo_destinatario=correo_destinatario,
            mensaje_para_destinatario=mensaje_para_destinatario,
        )

    def devolver_para_correccion(
        self,
        formulario_id: str,
        especificaciones: str,
        campos_identificados: List[str],
        acceso_service: "AccesoManualService",
        email_service: Optional[INotificador] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        formulario = self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        estado_anterior = formulario.estado
        dominio = FormularioDominio.desde_snapshot(formulario)
        dominio.devolver_para_correccion()

        campos_json = json.dumps(
            {"especificaciones": especificaciones, "campos": campos_identificados},
            ensure_ascii=False,
        )
        datos_acceso = acceso_service.reactivar_acceso_para_correccion(formulario_id)
        self._repo.actualizar_para_correccion(
            formulario_id,
            dominio.estado.value,
            dominio.numero_correccion,
            campos_json,
        )
        self._registrar(EventoAuditoria(
            formulario_id=formulario_id,
            tipo_evento=TipoEvento.FORMULARIO_DEVUELTO,
            estado_anterior=estado_anterior,
            estado_nuevo=dominio.estado.value,
            actor_id=actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata={
                "numero_correccion": dominio.numero_correccion,
                "especificaciones":  especificaciones,
                "campos":            campos_identificados,
            },
        ))
        self._alertar(
            TipoAlerta.FORMULARIO_DEVUELTO,
            formulario,
            detalle=f"Corrección #{dominio.numero_correccion}",
        )

        correo_notificado = datos_acceso["correo_destinatario"] if datos_acceso else None
        enlace_acceso     = datos_acceso["enlace_diligenciamiento"] if datos_acceso else None
        correo_enviado    = False
        if email_service and correo_notificado:
            correo_enviado = email_service.enviar_notificacion_devolucion(
                correo_destinatario=correo_notificado,
                especificaciones_correccion=especificaciones,
                enlace_diligenciamiento=enlace_acceso,
                campos_identificados=campos_identificados or None,
            )
        return {
            "estado":            dominio.estado.value,
            "correo_notificado": correo_notificado,
            "correo_enviado":    correo_enviado,
        }

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def resolver_documento_para_descarga(
        self,
        formulario_id: str,
        doc_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> InfoDescarga:
        self._buscar_formulario_expediente(formulario_id, contrapartes_permitidas)
        documento = self._buscar_documento_descargable(formulario_id, doc_id)
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        if not self._storage.existe(documento.ruta_archivo):
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        content_type = documento.content_type or "application/octet-stream"
        return self._storage.info_descarga(documento.ruta_archivo, documento.nombre_archivo, content_type)


def _html_reporte_comparacion(formulario, comparacion: Dict[str, Any]) -> str:
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    filas = "".join(
        f"""
        <tr>
          <td>{escape(cambio["etiqueta"])}</td>
          <td>{escape(cambio["valor_anterior"])}</td>
          <td>{escape(cambio["valor_corregido"])}</td>
        </tr>
        """
        for cambio in comparacion["cambios"]
    )
    if not filas:
        mensaje = comparacion.get("motivo") or "No se detectaron cambios en los campos comparables."
        filas = f'<tr><td colspan="3" class="sin-cambios">{escape(mensaje)}</td></tr>'

    return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; color: #0f172a; font-size: 12px; }}
        h1 {{ font-size: 20px; margin: 0 0 6px; }}
        .meta {{ color: #64748b; margin-bottom: 18px; }}
        .resumen {{ margin: 14px 0 18px; padding: 10px 12px; border: 1px solid #e2e8f0; background: #f8fafc; }}
        table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        th {{ text-align: left; background: #f1f5f9; color: #475569; font-size: 10px; text-transform: uppercase; padding: 8px; }}
        td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; vertical-align: top; word-wrap: break-word; }}
        .sin-cambios {{ text-align: center; color: #64748b; padding: 18px; }}
      </style>
    </head>
    <body>
      <h1>Evidencia de cambios corregidos</h1>
      <div class="meta">Generado: {escape(generado)}</div>
      <div class="resumen">
        <strong>Expediente:</strong> {escape(formulario.codigo_peticion or formulario.id)}<br>
        <strong>Razón social:</strong> {escape(formulario.razon_social or "Sin información")}<br>
        <strong>Comparación:</strong> v{comparacion["version_anterior"]} → v{comparacion["version_corregida"]}<br>
        <strong>Total de cambios:</strong> {comparacion["total_cambios"]}
      </div>
      <table>
        <thead>
          <tr>
            <th>Campo</th>
            <th>Antes</th>
            <th>Después</th>
          </tr>
        </thead>
        <tbody>{filas}</tbody>
      </table>
    </body>
    </html>
    """
