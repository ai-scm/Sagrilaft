"""Handler para carga de documentos a expedientes."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from domain.auditoria.entidades import ActorTipo, EventoAuditoria, TipoEvento
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_REPORTE_FINAL
from domain.excepciones import FormularioNoEncontradoError, SinPermisoError
from domain.formulario.entidades import FormularioDominio
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import IAlertasPortal, TipoAlerta
from domain.puertos.auditoria import RepositorioAuditoria
from domain.puertos.repositorios import RepositorioExpediente
from services.formulario.almacenamiento_contraparte import resolver_key_contraparte


@dataclass
class ComandoCargaDocumento:
    """Comando para cargar un documento a un expediente."""

    formulario_id: str
    archivo_bytes: bytes
    nombre_archivo: str
    content_type: str
    justificacion: str
    actor_id: str
    tipo_documento: str  # "FORMULARIO_PDF", "REPORTE_FINAL"
    contrapartes_permitidas: Optional[List[str]] = None


class ValidadorCargaDocumento:
    """Valida comandos de carga de documentos."""

    def validar(self, comando: ComandoCargaDocumento) -> None:
        """
        Valida el comando de carga.

        Raises:
            ValueError: Si la validación falla.
        """
        if comando.content_type != "application/pdf":
            raise ValueError("Solo se permite formato PDF.")

        if (
            comando.tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF
            and len(comando.justificacion.strip()) < 20
        ):
            raise ValueError("La justificación debe tener al menos 20 caracteres.")

        if not comando.archivo_bytes or len(comando.archivo_bytes) == 0:
            raise ValueError("El archivo está vacío.")

        if len(comando.archivo_bytes) > 50_000_000:  # 50MB
            raise ValueError("El archivo excede el tamaño máximo de 50MB.")


class CargaDocumentoHandler:
    """
    Orquestador de carga de documentos en expedientes.

    Responsabilidades:
      - Validar comando de carga
      - Persistir archivo en storage
      - Registrar documento en BD
      - Actualizar estado del formulario
      - Registrar auditoría
      - Alertar al portal
    """

    _ESTADOS_EXPEDIENTE = [
        EstadoFormulario.ENVIADO,
        EstadoFormulario.EN_CORRECCION,
        EstadoFormulario.VALIDADO,
        EstadoFormulario.RECHAZADO,
        EstadoFormulario.PENDIENTE_FIRMA,
        EstadoFormulario.FIRMADO,
        EstadoFormulario.CERRADO,
    ]

    def __init__(
        self,
        repo_expediente: RepositorioExpediente,
        documentos_service: Any,  # DocumentoService
        validador: Optional[ValidadorCargaDocumento] = None,
        auditoria_service: Optional[RepositorioAuditoria] = None,
        alertas_service: Optional[IAlertasPortal] = None,
    ) -> None:
        self._repo = repo_expediente
        self._documentos = documentos_service
        self._validador = validador or ValidadorCargaDocumento()
        self._auditoria = auditoria_service
        self._alertas = alertas_service

    def ejecutar(self, comando: ComandoCargaDocumento) -> Dict[str, Any]:
        """
        Ejecuta la carga del documento.

        Args:
            comando: Comando con parámetros de carga

        Returns:
            Dict con estado y número de versión

        Raises:
            ValueError: Si el comando no es válido
            FormularioNoEncontradoError: Si el formulario no existe
            SinPermisoError: Si el usuario no tiene acceso
        """
        # 1. Validar
        self._validador.validar(comando)

        # 2. Buscar y validar acceso al formulario
        formulario = self._buscar_formulario_validado(
            comando.formulario_id,
            comando.contrapartes_permitidas,
        )
        estado_anterior = formulario.estado

        # 3. Determinar nueva versión y detalles de guardado
        versionamiento = self._obtener_versionamiento(
            comando.formulario_id,
            comando.tipo_documento,
        )

        # 4. Guardar archivo
        prefijo = self._resolver_prefijo_almacenamiento(formulario, comando.tipo_documento)
        key_archivo = self._construir_key_archivo(
            prefijo, comando.nombre_archivo, comando.tipo_documento
        )
        self._documentos.guardar_archivo(
            key_archivo,
            comando.archivo_bytes,
            comando.content_type,
        )

        # 5. Registrar documento en BD
        self._documentos.registrar_documento_en_bd(
            formulario_id=comando.formulario_id,
            tipo_documento=comando.tipo_documento,
            nombre_archivo=comando.nombre_archivo,
            key=key_archivo,
            content_type=comando.content_type,
            tamano=len(comando.archivo_bytes),
            hash_sha256=self._documentos.calcular_hash(comando.archivo_bytes),
            subido_por=comando.actor_id,
            version_numero=versionamiento["numero_version"],
            version_anterior_id=versionamiento.get("version_anterior_id"),
        )

        # 6. Transicionar estado del formulario
        estado_nuevo = self._transicionar_estado(formulario, comando.tipo_documento)
        self._repo.actualizar_estado(comando.formulario_id, estado_nuevo)

        # 7. Registrar auditoría
        self._registrar_auditoria(
            comando,
            formulario,
            estado_anterior,
            estado_nuevo,
            versionamiento["numero_version"],
        )

        # 8. Alertar al portal
        self._alertar_portal(comando, formulario)

        return {
            "estado": estado_nuevo,
            "version_numero": versionamiento["numero_version"],
        }

    # ─── Métodos privados ────────────────────────────────────────────────────

    def _buscar_formulario_validado(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]],
    ):
        """Busca formulario con validaciones de existencia y acceso."""
        formulario = self._repo.obtener(formulario_id, self._ESTADOS_EXPEDIENTE)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        if (
            contrapartes_permitidas is not None
            and formulario.tipo_contraparte not in contrapartes_permitidas
        ):
            raise SinPermisoError(formulario.tipo_contraparte)
        return formulario

    def _obtener_versionamiento(
        self, formulario_id: str, tipo_documento: str
    ) -> Dict[str, Any]:
        """Determina número de versión y referencia a versión anterior."""
        documento_anterior = None

        # Obtener documento anterior según tipo
        if tipo_documento == TIPO_DOCUMENTO_FORMULARIO_PDF:
            documento_anterior = self._documentos.obtener_ultimo_formulario_pdf(
                formulario_id
            )
        elif tipo_documento == TIPO_DOCUMENTO_REPORTE_FINAL:
            # Buscar el último reporte final en la lista de documentos
            documentos = self._documentos.listar_documentos(formulario_id)
            reportes = [
                d
                for d in documentos
                if d.tipo_documento == TIPO_DOCUMENTO_REPORTE_FINAL
            ]
            if reportes:
                documento_anterior = max(reportes, key=lambda d: d.version_numero)

        if documento_anterior:
            numero_version = documento_anterior.version_numero + 1
            version_anterior_id = documento_anterior.id
        else:
            numero_version = 1
            version_anterior_id = None

        return {
            "numero_version": numero_version,
            "version_anterior_id": version_anterior_id,
        }

    def _resolver_prefijo_almacenamiento(self, formulario, tipo_documento: str) -> str:
        """Resuelve el prefijo de almacenamiento según tipo de documento."""
        prefijo = resolver_key_contraparte(
            formulario.tipo_contraparte, formulario.razon_social
        )

        if tipo_documento == "REPORTE_FINAL":
            prefijo = f"{prefijo}/reportes_finales"

        return prefijo

    def _construir_key_archivo(
        self, prefijo: str, nombre_archivo: str, tipo_documento: str
    ) -> str:
        """Construye la clave completa de almacenamiento."""
        return f"{prefijo}/{nombre_archivo}"

    def _transicionar_estado(self, formulario, tipo_documento: str) -> str:
        """Determina el nuevo estado según el tipo de documento."""
        dominio = FormularioDominio.desde_snapshot(formulario)

        if tipo_documento == "FORMULARIO_PDF":
            dominio.carga_manual()
        elif tipo_documento == "REPORTE_FINAL":
            dominio.cerrar_con_reporte()

        return dominio.estado.value

    def _registrar_auditoria(
        self,
        comando: ComandoCargaDocumento,
        formulario,
        estado_anterior: str,
        estado_nuevo: str,
        numero_version: int,
    ) -> None:
        """Registra evento de auditoría si está disponible."""
        if not self._auditoria:
            return

        # Mapear tipo de evento según tipo de documento
        tipo_evento_map = {
            "FORMULARIO_PDF": TipoEvento.FORMULARIO_CARGADO_MANUALMENTE,
            "REPORTE_FINAL": TipoEvento.REPORTE_FINAL_CARGADO,
        }
        tipo_evento = tipo_evento_map.get(
            comando.tipo_documento, TipoEvento.FORMULARIO_CARGADO_MANUALMENTE
        )

        # Construir metadata según tipo
        metadata = {
            "upload_method": "MANUAL",
            "upload_reason": comando.justificacion.strip(),
            "version": numero_version,
        }

        evento = EventoAuditoria(
            formulario_id=comando.formulario_id,
            tipo_evento=tipo_evento,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            actor_id=comando.actor_id,
            actor_tipo=ActorTipo.OPERADOR,
            metadata=metadata,
        )
        self._auditoria.registrar_evento(evento)

    def _alertar_portal(
        self, comando: ComandoCargaDocumento, formulario
    ) -> None:
        """Dispara alerta al portal si está disponible."""
        if not self._alertas:
            return

        alerta_por_tipo_documento = {
            "FORMULARIO_PDF": TipoAlerta.FORMULARIO_RECIBIDO,
            "REPORTE_FINAL": TipoAlerta.REPORTE_FINAL_CARGADO,
        }
        detalle_por_tipo_documento = {
            "FORMULARIO_PDF": "Carga manual de formulario",
            "REPORTE_FINAL": "Carga de reporte final",
        }

        self._alertas.alertar(
            tipo=alerta_por_tipo_documento.get(
                comando.tipo_documento,
                TipoAlerta.FORMULARIO_RECIBIDO,
            ),
            formulario_id=formulario.id,
            razon_social=formulario.razon_social or "",
            tipo_contraparte=formulario.tipo_contraparte or "",
            codigo_peticion=formulario.codigo_peticion,
            detalle=detalle_por_tipo_documento.get(
                comando.tipo_documento,
                "Carga de documento",
            ),
        )
