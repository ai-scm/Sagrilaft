"""
CRUD de documentos adjuntos — delegación a IAlmacenamiento para el archivo físico.

ruta_archivo en BD almacena la KEY relativa al backend (ej. 'CLIENTES/Empresa/rut.pdf').
La key es agnóstica al backend de almacenamiento concreto.
"""

import hashlib
import re
from pathlib import Path
from typing import List

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
        """Key temporal en el backend mientras el formulario está en borrador."""
        return f"{codigo_peticion}/{_sanitizar_nombre_archivo(nombre_archivo)}"

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
    ) -> DocumentoDatos:
        """Crea y persiste el registro del documento en la BD."""
        return self._repo.crear({
            "formulario_id": formulario_id,
            "tipo_documento": tipo_documento,
            "nombre_archivo": nombre_archivo,
            "ruta_archivo":   key,
            "content_type":   content_type,
            "tamano":         tamano,
            "hash_sha256":    hash_sha256,
            "subido_por":     subido_por,
        })

    # ─── Movimiento (borrador → contraparte) ───────────────────────────────────

    def mover_archivos_formulario_a_contraparte(
        self, formulario_id: str, prefijo_destino: str
    ) -> None:
        """
        Mueve los archivos del borrador al prefijo definitivo de la contraparte
        y actualiza las rutas en BD en una sola operación.
        """
        documentos = self.listar_documentos(formulario_id)
        if not documentos:
            return

        rutas_nuevas: dict[str, str] = {}
        for doc in documentos:
            key_actual = doc.ruta_archivo
            nombre = Path(key_actual).name
            key_nuevo = f"{prefijo_destino}/{nombre}"
            if key_actual != key_nuevo:
                self._storage.mover(key_actual, key_nuevo)
                rutas_nuevas[doc.id] = key_nuevo

        if rutas_nuevas:
            self._repo.actualizar_rutas(rutas_nuevas)

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
        """Elimina el archivo del backend y lo marca como eliminado en BD."""
        documento = self.buscar_documento(formulario_id, doc_id)
        self._storage.eliminar(documento.ruta_archivo)
        self._repo.marcar_eliminado(doc_id)
