"""
CRUD de documentos adjuntos — delegación a IAlmacenamiento para el archivo físico.

ruta_archivo en BD almacena la KEY relativa al backend (ej. 'CLIENTES/Empresa/rut.pdf').
La key es agnóstica al backend de almacenamiento concreto.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from domain.constantes import TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT
from domain.contratos import DocumentoDatos
from domain.excepciones import DocumentoNoEncontradoError
from domain.puertos.repositorios import RepositorioDocumento
from domain.puertos.almacenamiento import IAlmacenamiento, InfoDescarga


def _sanitizar_nombre_archivo(nombre: str) -> str:
    """
    Elimina vectores de path traversal y caracteres peligrosos.

    OWASP A05: Path.name extrae solo la parte final del nombre, bloqueando '../'.
    La expresión regular retiene únicamente caracteres seguros para el filesystem.
    """
    nombre_base = Path(nombre).name
    nombre_limpio = re.sub(r"[^\w.\-]", "_", nombre_base)
    return nombre_limpio or "archivo"


class DocumentoService:
    """CRUD y manejo de archivos para los documentos adjuntos de un formulario."""

    def __init__(self, repo: RepositorioDocumento, storage: IAlmacenamiento) -> None:
        self._repo = repo
        self._storage = storage

    # ─── Keys ─────────────────────────────────────────────────────────────────

    def key_borrador(self, codigo_peticion: str, nombre_archivo: str) -> str:
        """Key temporal (espacio efímero). Al estar en tmp/, S3 lo borra automáticamente en 7 días si es abandonado."""
        return f"tmp/{codigo_peticion}/{_sanitizar_nombre_archivo(nombre_archivo)}"

    # ─── Escritura ─────────────────────────────────────────────────────────────

    @staticmethod
    def calcular_hash(contenido: bytes) -> str:
        """Calcula el hash SHA-256 de un contenido para verificación de integridad."""
        return hashlib.sha256(contenido).hexdigest()

    def guardar_archivo(self, key: str, contenido: bytes, content_type: str = "") -> None:
        """Persiste el contenido binario en el backend bajo la key indicada."""
        self._storage.guardar(key, contenido, content_type)

    def guardar_desde_archivo_local(self, key: str, ruta_local: Path, content_type: str = "") -> None:
        """Sube un archivo ya existente en disco al backend (util para PDFs generados)."""
        self._storage.guardar_desde_archivo_local(key, ruta_local, content_type)

    def registrar_documento_en_bd(
        self,
        formulario_id: str,
        tipo_documento: str,
        nombre_archivo: str,
        key: str,
        content_type: str,
        tamano: int,
        hash_sha256: str | None = None,
        subido_por: str | None = None,
        version_numero: int = 1,
        version_anterior_id: str | None = None,
        snapshot_datos: Dict[str, Any] | None = None,
    ) -> DocumentoDatos:
        """Crea y persiste el registro del documento en la BD."""
        return self._repo.crear({
            "formulario_id":      formulario_id,
            "tipo_documento":     tipo_documento,
            "nombre_archivo":     nombre_archivo,
            "ruta_archivo":       key,
            "content_type":       content_type,
            "tamano":             tamano,
            "hash_sha256":        hash_sha256,
            "subido_por":         subido_por,
            "version_numero":     version_numero,
            "version_anterior_id": version_anterior_id,
            "snapshot_datos":      snapshot_datos,
        })

    def obtener_ultimo_formulario_pdf(self, formulario_id: str) -> DocumentoDatos | None:
        """
        Retorna el PDF del formulario con el mayor version_numero activo.

        Se usa antes de generar un nuevo PDF para encadenar la versión nueva
        con la anterior mediante version_anterior_id.
        """
        return self._repo.obtener_ultimo_formulario_pdf(formulario_id)

    def actualizar_snapshot_datos(self, doc_id: str, snapshot_datos: str) -> None:
        """Actualiza el campo snapshot_datos del documento en la BD."""
        self._repo.actualizar_snapshot_datos(doc_id, snapshot_datos)

    # ─── Movimiento (borrador → contraparte) ───────────────────────────────────

    def mover_archivos_formulario_a_contraparte(
        self, formulario_id: str, prefijo_destino: str
    ) -> None:
        """
        Mueve los archivos del borrador al prefijo definitivo de la contraparte
        y actualiza las rutas en BD en una sola operación.
        Limpia el directorio temporal vacío después de mover todos los archivos.
        """
        logger = logging.getLogger(__name__)
        logger.info(f"[MOVER] Inicio: formulario_id={formulario_id}, prefijo_destino={prefijo_destino}")
        
        documentos = self.listar_documentos(formulario_id)
        logger.info(f"[MOVER] Documentos encontrados: {len(documentos)}")
        if not documentos:
            logger.warning(f"[MOVER] No hay documentos para mover en {formulario_id}")
            return

        # Extrae la carpeta origen (ej: "tmp/SAG-705A5125" de "tmp/SAG-705A5125/archivo.pdf")
        prefijo_origen = str(Path(documentos[0].ruta_archivo).parent) if len(Path(documentos[0].ruta_archivo).parts) > 1 else None

        rutas_nuevas: dict[str, str] = {}
        for doc in documentos:
            if doc.tipo_documento == TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT:
                logger.info("[MOVER] Se omite certificado SAGRILAFT de auditoria: %s", doc.ruta_archivo)
                continue

            key_actual = doc.ruta_archivo
            nombre = Path(key_actual).name
            key_nuevo = f"{prefijo_destino}/{nombre}"
            logger.info(f"[MOVER] {key_actual} -> {key_nuevo}")
            if key_actual != key_nuevo:
                if not self._storage.existe(key_actual):
                    logger.warning("[MOVER] Se omite archivo inexistente en storage: %s", key_actual)
                    continue
                self._storage.mover(key_actual, key_nuevo)
                rutas_nuevas[doc.id] = key_nuevo
            else:
                logger.info(f"[MOVER] Archivo ya está en destino: {key_actual}")

        if rutas_nuevas:
            self._repo.actualizar_rutas(rutas_nuevas)
            logger.info(f"[MOVER] Rutas actualizadas en BD: {len(rutas_nuevas)}")

        # Limpia el directorio temporal vacío (prefijo origen del borrador)
        if prefijo_origen:
            logger.info(f"[MOVER] Intentando limpiar directorio origen: {prefijo_origen}")
            self._storage.limpiar_directorio_vacio(prefijo_origen)
        logger.info(f"[MOVER] Fin: {formulario_id}")

    # ─── Lectura ───────────────────────────────────────────────────────────────

    def buscar_documento(self, formulario_id: str, doc_id: str) -> DocumentoDatos:
        documento = self._repo.buscar(formulario_id, doc_id)
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        return documento

    def listar_documentos(self, formulario_id: str) -> List[DocumentoDatos]:
        return self._repo.listar_activos(formulario_id)

    def leer_bytes(self, key: str) -> bytes:
        """Lee el contenido de un archivo — usado para enviar PDFs a ZohoSign."""
        return self._storage.leer(key)

    def info_descarga(self, doc: DocumentoDatos) -> InfoDescarga:
        """Genera la info de descarga (URL prefirmada o ruta local según backend)."""
        if not self._storage.existe(doc.ruta_archivo):
            raise DocumentoNoEncontradoError("", doc.id)
        return self._storage.info_descarga(
            doc.ruta_archivo,
            doc.nombre_archivo,
            doc.content_type or "application/octet-stream",
        )

    # ─── Eliminación ───────────────────────────────────────────────────────────

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        """
        Soft-delete en BD. Solo elimina el archivo físico si está en la carpeta 'tmp/' (borrador).
        Los documentos oficiales (enviados) se conservan en storage por auditoría.
        """
        documento = self.buscar_documento(formulario_id, doc_id)
        if documento.ruta_archivo.startswith("tmp/"):
            self._storage.eliminar(documento.ruta_archivo)
        self._repo.marcar_eliminado(doc_id)

    def reemplazar_documento_anterior(
        self, formulario_id: str, tipo_documento: str
    ) -> tuple[int, str | None]:
        """
        Busca el documento activo del mismo tipo CON bloqueo, lo elimina
        y retorna (version_numero, version_anterior_id) para el nuevo.

        Atómico: el FOR UPDATE impide que dos requests concurrentes
        lean la misma versión anterior.
        """
        doc_anterior = self._repo.obtener_activo_por_tipo_con_bloqueo(
            formulario_id, tipo_documento
        )
        if not doc_anterior:
            return 1, None

        version_numero = doc_anterior.version_numero + 1
        version_anterior_id = doc_anterior.id
        self.eliminar_documento(formulario_id, doc_anterior.id)
        return version_numero, version_anterior_id
