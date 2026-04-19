"""
Módulo para la persistencia de documentos en base de datos y sistema de archivos.
"""

import os
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from datetime import datetime, timezone


from models import DocumentoAdjunto
from core.configuracion import load_config
from domain.excepciones import DocumentoNoEncontradoError

CONFIG = load_config()


class DocumentoService:
    """
    CRUD y manejo de archivos en disco para los documentos adjuntos de un formulario.
    """

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion
        self.directorio_base = CONFIG.upload_dir
        self._validar_directorio_produccion()

    def _validar_directorio_produccion(self):
        """Previene fallas críticas antes de aceptar tráfico."""
        if not self.directorio_base.exists():
            self.directorio_base.mkdir(parents=True, exist_ok=True)
            
        if not os.access(self.directorio_base, os.W_OK):
            raise PermissionError(f"CRÍTICO: El volumen de uploads {self.directorio_base} no tiene permisos de escritura.")

    def guardar_archivo_en_disco(
        self, formulario_id: str, nombre_archivo: str, contenido: bytes
    ) -> Path:
        """Persiste el contenido binario en el directorio de uploads."""
        directorio = self.directorio_base / formulario_id
        directorio.mkdir(parents=True, exist_ok=True)
        ruta = directorio / nombre_archivo
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
        """
        Elimina un documento adjunto de disco y de la BD de forma lógica.
        """
        documento = self.buscar_documento(formulario_id, doc_id)
        ruta = Path(documento.ruta_archivo)
        if ruta.exists():
            ruta.unlink()
        
        documento.deleted_at = datetime.now(timezone.utc)
        self._sesion.commit()

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        """
        Lista todos los documentos adjuntos activos de un formulario.
        """
        return self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.formulario_id == formulario_id,
            DocumentoAdjunto.deleted_at.is_(None)
        ).all()
