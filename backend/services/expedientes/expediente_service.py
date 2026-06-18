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
from domain.catalogo_correcciones import resolver_etiquetas_campos_corregibles
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
        
        # Construir detalle con campos que requieren corrección
        etiquetas_campos = resolver_etiquetas_campos_corregibles(campos_identificados or [])
        detalle_alerta = f"Corrección #{dominio.numero_correccion}\n"
        if etiquetas_campos:
            detalle_alerta += "\nCampos que requieren corrección:\n" + "\n".join(f"• {etiqueta}" for etiqueta in etiquetas_campos)
        
        self._alertar(
            TipoAlerta.FORMULARIO_DEVUELTO,
            formulario,
            detalle=detalle_alerta.strip(),
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


def _obtener_configuracion_comparador(nombre_campo: str) -> Dict[str, Any]:
    """Obtiene configuración de campos para un tipo de registro complejo."""
    return {
        'junta_directiva': {
            'tipo': 'arregloObjetos',
            'campos': [
                {'clave': 'nombre', 'etiqueta': 'Nombre'},
                {'clave': 'cargo', 'etiqueta': 'Cargo'},
                {'clave': 'tipo_id', 'etiqueta': 'Tipo ID'},
                {'clave': 'numero_id', 'etiqueta': 'Número ID'},
                {'clave': 'es_pep', 'etiqueta': 'PEP'},
                {'clave': 'vinculos_pep', 'etiqueta': 'Vínculos PEP'},
            ]
        },
        'accionistas': {
            'tipo': 'arregloObjetos',
            'campos': [
                {'clave': 'nombre', 'etiqueta': 'Nombre'},
                {'clave': 'tipo_id', 'etiqueta': 'Tipo ID'},
                {'clave': 'numero_id', 'etiqueta': 'Número ID'},
                {'clave': 'porcentaje', 'etiqueta': 'Porcentaje'},
                {'clave': 'es_pep', 'etiqueta': 'PEP'},
                {'clave': 'vinculos_pep', 'etiqueta': 'Vínculos PEP'},
            ]
        },
        'beneficiario_final': {
            'tipo': 'arregloObjetos',
            'campos': [
                {'clave': 'nombre', 'etiqueta': 'Nombre'},
                {'clave': 'tipo_id', 'etiqueta': 'Tipo ID'},
                {'clave': 'numero_id', 'etiqueta': 'Número ID'},
                {'clave': 'porcentaje', 'etiqueta': 'Porcentaje'},
                {'clave': 'es_pep', 'etiqueta': 'PEP'},
                {'clave': 'vinculos_pep', 'etiqueta': 'Vínculos PEP'},
            ]
        },
        'referencias_comerciales': {
            'tipo': 'arregloObjetos',
            'campos': [
                {'clave': 'nombre_establecimiento', 'etiqueta': 'Establecimiento'},
                {'clave': 'ciudad', 'etiqueta': 'Ciudad'},
                {'clave': 'persona_contacto', 'etiqueta': 'Persona de contacto'},
                {'clave': 'telefono', 'etiqueta': 'Teléfono'},
            ]
        },
        'referencias_bancarias': {
            'tipo': 'arregloObjetos',
            'campos': [
                {'clave': 'entidad', 'etiqueta': 'Entidad'},
                {'clave': 'producto', 'etiqueta': 'Producto'},
            ]
        },
        'tipos_transaccion': {
            'tipo': 'arregloSimple',
            'etiquetasValores': {
                'importacion': 'Importación',
                'exportacion': 'Exportación',
                'inversiones': 'Inversiones',
                'pago_servicios': 'Pago de servicios',
                'otras': 'Otras',
            }
        },
    }.get(nombre_campo, {'tipo': 'arregloObjetos', 'campos': []})


def _es_campo_complejo(nombre_campo: str) -> bool:
    """Determina si un campo requiere visualización como fichas o arreglo."""
    return nombre_campo in {
        'junta_directiva',
        'accionistas',
        'beneficiario_final',
        'referencias_comerciales',
        'referencias_bancarias',
        'tipos_transaccion',
    }


def _parsear_arreglo_valores(valor: Any) -> list:
    """Parsea un valor a arreglo, manejando strings JSON y errores."""
    import json
    if not valor or valor == "Sin información":
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        try:
            arregloParsado = json.loads(valor)
            if isinstance(arregloParsado, list):
                return arregloParsado
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _son_valores_iguales(valor_a: Any, valor_b: Any) -> bool:
    """Comprueba si dos valores son iguales tras normalización."""
    str_a = (str(valor_a) if valor_a is not None else '').strip().lower()
    str_b = (str(valor_b) if valor_b is not None else '').strip().lower()
    return str_a == str_b


def _formatear_valor_campo(valor: Any, clave: str) -> str:
    """Formatea un valor según el tipo de campo."""
    if valor is None or valor == '':
        return ''
    if clave == 'porcentaje':
        try:
            numero = float(valor)
            return f'{numero}%'
        except (ValueError, TypeError):
            return str(valor)
    return str(valor)


def _generar_html_arreglo_simple(
    valoresAntes: list,
    valoresDespues: list,
    configuracion: Dict[str, Any],
) -> str:
    """Genera HTML para comparación de arreglos simples (lista de strings)."""
    from html import escape
    
    conjuntoAntes = set(valoresAntes)
    conjuntoDespues = set(valoresDespues)
    
    valoresEliminados = [v for v in valoresAntes if v not in conjuntoDespues]
    valoresNuevos = [v for v in valoresDespues if v not in conjuntoAntes]
    valoresIguales = [v for v in valoresAntes if v in conjuntoDespues]
    
    etiquetasValores = configuracion.get('etiquetasValores', {})
    
    html = []
    
    if valoresEliminados:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #dc2626; margin-bottom: 6px; font-size: 11px;">Eliminados:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresEliminados:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #fff7ed; border: 1px solid #fed7aa; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #7c2d12;">{escape(etiqueta)}</span>')
        html.append('</div></div>')
    
    if valoresIguales:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #666; margin-bottom: 6px; font-size: 11px;">Sin cambios:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresIguales:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #475569;">{escape(etiqueta)}</span>')
        html.append('</div></div>')
    
    if valoresNuevos:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #16a34a; margin-bottom: 6px; font-size: 11px;">Agregados:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresNuevos:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #166534;">{escape(etiqueta)}</span>')
        html.append('</div></div>')
    
    return ''.join(html)


def _generar_fichas_registro_comparadas(
    nombre_campo: str,
    valor_anterior: Any,
    valor_corregido: Any,
) -> str:
    """Genera HTML de fichas para registros complejos (objetos o simples)."""
    from html import escape
    
    configuracion = _obtener_configuracion_comparador(nombre_campo)
    registrosAntes = _parsear_arreglo_valores(valor_anterior)
    registrosDespues = _parsear_arreglo_valores(valor_corregido)
    
    if not registrosAntes and not registrosDespues:
        return '<div style="padding: 8px; color: #64748b;">Sin datos para mostrar.</div>'
    
    # Manejar arreglos simples (lista de strings)
    if configuracion.get('tipo') == 'arregloSimple':
        valoresAntes = [v for v in registrosAntes if isinstance(v, str)]
        valoresDespues = [v for v in registrosDespues if isinstance(v, str)]
        return _generar_html_arreglo_simple(valoresAntes, valoresDespues, configuracion)
    
    # Manejar arreglos de objetos (fichas)
    pares = []
    for indice in range(max(len(registrosAntes), len(registrosDespues))):
        registroAntes = registrosAntes[indice] if indice < len(registrosAntes) else None
        registroDespues = registrosDespues[indice] if indice < len(registrosDespues) else None
        if registroAntes or registroDespues:
            pares.append({
                'antes': registroAntes,
                'despues': registroDespues,
                'esNuevo': not registroAntes,
                'esEliminado': not registroDespues,
            })
    
    htmlFichas = []
    for indice, parRegistro in enumerate(pares):
        etiqueta = 'Nuevo' if parRegistro['esNuevo'] else 'Eliminado' if parRegistro['esEliminado'] else f'Registro {indice + 1}'
        numeroId = (parRegistro['antes'] or {}).get('numero_id') or (parRegistro['despues'] or {}).get('numero_id') or ''
        
        filasTabla = []
        for campoDef in configuracion.get('campos', []):
            clave = campoDef['clave']
            etiquetaCampo = campoDef['etiqueta']
            valorAntes = (parRegistro['antes'] or {}).get(clave, '') if parRegistro['antes'] else ''
            valorDespues = (parRegistro['despues'] or {}).get(clave, '') if parRegistro['despues'] else ''
            seModifico = not _son_valores_iguales(valorAntes, valorDespues)
            
            bgAntes = '#fff7ed' if (seModifico and parRegistro['antes']) else '#fff'
            bgDespues = '#f0fdf4' if (seModifico and parRegistro['despues']) else '#fff'
            
            filasTabla.append(f'''
                <tr>
                  <td style="padding: 6px 8px; color: #64748b; font-size: 11px; width: 30%;">{escape(etiquetaCampo)}</td>
                  <td style="padding: 6px 8px; background: {bgAntes}; width: 35%;">{escape(_formatear_valor_campo(valorAntes, clave))}</td>
                  <td style="padding: 6px 8px; background: {bgDespues}; width: 35%;">{escape(_formatear_valor_campo(valorDespues, clave))}</td>
                </tr>
            ''')
        
        htmlFicha = f'''
        <div style="border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px; margin-bottom: 10px; background: #fff;">
          <div style="font-weight: bold; color: #1e293b; margin-bottom: 8px; display: flex; justify-content: space-between;">
            <span>{escape(etiqueta)}</span>
            <span style="font-size: 11px; color: #64748b;">{escape(numeroId)}</span>
          </div>
          <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
            {''.join(filasTabla)}
          </table>
        </div>
        '''
        htmlFichas.append(htmlFicha)
    
    return ''.join(htmlFichas)


def _html_reporte_comparacion(formulario, comparacion: Dict[str, Any]) -> str:
    """Genera HTML para reporte de comparación de cambios."""
    from html import escape
    
    generadoEn = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    filasHtml = []
    for cambio in comparacion["cambios"]:
        if _es_campo_complejo(cambio["campo"]):
            fichasHtml = _generar_fichas_registro_comparadas(
                cambio["campo"],
                cambio["valor_anterior"],
                cambio["valor_corregido"],
            )
            filasHtml.append(f'''
            <tr>
              <td colspan="3" style="padding: 0; border: none;">
                <div style="padding: 10px 8px;">
                  <div style="font-weight: bold; color: #0f172a; margin-bottom: 10px;">{escape(cambio["etiqueta"])}</div>
                  {fichasHtml}
                </div>
              </td>
            </tr>
            ''')
        else:
            filasHtml.append(f'''
            <tr>
              <td>{escape(cambio["etiqueta"])}</td>
              <td>{escape(cambio["valor_anterior"])}</td>
              <td>{escape(cambio["valor_corregido"])}</td>
            </tr>
            ''')
    
    contenidoFilas = "".join(filasHtml)
    if not contenidoFilas:
        mensajeVacio = comparacion.get("motivo") or "No se detectaron cambios en los campos comparables."
        contenidoFilas = f'<tr><td colspan="3" class="sin-cambios">{escape(mensajeVacio)}</td></tr>'

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
      <div class="meta">Generado: {escape(generadoEn)}</div>
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
        <tbody>{contenidoFilas}</tbody>
      </table>
    </body>
    </html>
    """
