"""
Persistencia de documentos en base de datos y sistema de archivos.
"""

import os
import re
import shutil
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session
from datetime import datetime, timezone

from infrastructure.persistencia.models import DocumentoAdjunto
from domain.excepciones import DocumentoNoEncontradoError


def _sanitizar_nombre_archivo(nombre: str) -> str:
    """
    Elimina vectores de path traversal y caracteres peligrosos del nombre de archivo.

    OWASP A05 — Security Misconfiguration / Path Traversal:
    Un cliente puede enviar '../../etc/passwd' como filename. Path.name extrae
    solo la parte final, y la expresión regular retiene únicamente caracteres
    seguros para el sistema de archivos.
    """
    nombre_base = Path(nombre).name
    nombre_limpio = re.sub(r"[^\w.\-]", "_", nombre_base)
    return nombre_limpio or "archivo"


class DocumentoService:
    """
    CRUD y manejo de archivos en disco para los documentos adjuntos de un formulario.
    """

    def __init__(self, sesion: Session, upload_dir: Path) -> None:
        self._sesion = sesion
        self.directorio_base = upload_dir
        self._validar_directorio_produccion()

    def _validar_directorio_produccion(self) -> None:
        """Previene fallas críticas antes de aceptar tráfico."""
        if not self.directorio_base.exists():
            self.directorio_base.mkdir(parents=True, exist_ok=True)
        if not os.access(self.directorio_base, os.W_OK):
            raise PermissionError(
                f"CRÍTICO: El volumen de uploads {self.directorio_base} no tiene permisos de escritura."
            )

    def ruta_directorio_borrador(self, codigo_peticion: str) -> Path:
        """Directorio temporal de trabajo mientras el formulario está en borrador."""
        return self.directorio_base / codigo_peticion

    def guardar_archivo_en_disco(
        self, directorio_destino: Path, nombre_archivo: str, contenido: bytes
    ) -> Path:
        """Persiste el contenido binario en el directorio indicado.

        El nombre de archivo se sanitiza antes de construir la ruta para
        prevenir path traversal (OWASP A05).
        """
        nombre_seguro = _sanitizar_nombre_archivo(nombre_archivo)
        directorio_destino.mkdir(parents=True, exist_ok=True)
        ruta = directorio_destino / nombre_seguro
        ruta.write_bytes(contenido)
        return ruta

    def registrar_documento_en_bd(
        self,
        formulario_id: str,
        tipo_documento: str,
        nombre_archivo: str,
        ruta_archivo: Path,
        content_type: str,
        tamano: int,
    ) -> DocumentoAdjunto:
        """Crea y persiste el registro de un documento adjunto en la BD."""
        documento = DocumentoAdjunto(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            ruta_archivo=str(ruta_archivo),
            content_type=content_type,
            tamano=tamano,
        )
        self._sesion.add(documento)
        self._sesion.commit()
        self._sesion.refresh(documento)
        return documento

    def mover_archivos_formulario_a_contraparte(
        self, formulario_id: str, ruta_destino: Path
    ) -> None:
        """
        Mueve todos los archivos activos del formulario al directorio de la contraparte
        y actualiza las rutas en BD.
        """
        documentos = self.listar_documentos(formulario_id)
        if not documentos:
            return

        directorio_origen = Path(documentos[0].ruta_archivo).parent

        for doc in documentos:
            ruta_actual = Path(doc.ruta_archivo)
            ruta_nueva = ruta_destino / ruta_actual.name
            if ruta_actual != ruta_nueva:
                if ruta_actual.exists():
                    shutil.move(str(ruta_actual), str(ruta_nueva))
                doc.ruta_archivo = str(ruta_nueva)

        self._sesion.commit()

        if directorio_origen.exists() and not any(directorio_origen.iterdir()):
            directorio_origen.rmdir()

    def buscar_documento(self, formulario_id: str, doc_id: str) -> DocumentoAdjunto:
        """Recupera un documento adjunto por ID y formulario, o lanza DocumentoNoEncontradoError."""
        documento = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.id == doc_id,
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .first()
        )
        if not documento:
            raise DocumentoNoEncontradoError(formulario_id, doc_id)
        return documento

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        """Elimina un documento adjunto de disco y lo marca como eliminado en BD."""
        documento = self.buscar_documento(formulario_id, doc_id)
        ruta = Path(documento.ruta_archivo)
        if ruta.exists():
            ruta.unlink()
        documento.deleted_at = datetime.now(timezone.utc)
        self._sesion.commit()

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        """Lista todos los documentos adjuntos activos de un formulario."""
        return (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .all()
        )
