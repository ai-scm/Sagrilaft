"""
Operaciones de almacenamiento para el flujo de firma electrónica.

Funciones puras de keys y filesystem — sin dependencias de DB ni servicios.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from domain.formulario.entidades import FormularioDatos
from domain.puertos.almacenamiento import IAlmacenamiento
from services.formulario.almacenamiento_contraparte import resolver_key_contraparte

logger = logging.getLogger(__name__)

_NOMBRE_PDF_FIRMADO     = "formulario_firmado.pdf"
_NOMBRE_PDF_CERTIFICADO = "certificado_sagrilaft.pdf"


def resolver_key_documento_firmado(formulario: FormularioDatos) -> str:
    """Devuelve la key del backend donde se guarda el PDF firmado del formulario."""
    prefijo = resolver_key_contraparte(
        tipo_contraparte=formulario.tipo_contraparte or "",
        razon_social=formulario.razon_social or "",
    )
    return f"{prefijo}/{_NOMBRE_PDF_FIRMADO}"


def resolver_ruta_certificado(pdf_local: Path) -> Path:
    """Ruta local del certificado SAGRILAFT junto al PDF (solo para operaciones temp)."""
    return pdf_local.parent / _NOMBRE_PDF_CERTIFICADO


def archivar_en_storage(
    storage: IAlmacenamiento,
    key_actual: str,
) -> None:
    """
    Mueve el documento firmado existente a una key con sello de fecha/hora
    antes de guardar la versión corregida.

    Convención:  CLIENTES/Empresa/formulario_firmado_corregido_YYYYMMDD_HHMMSS.pdf
    Si el archivo no existe en el backend, el archivado se omite sin error.
    """
    if not storage.existe(key_actual):
        logger.warning("Archivo previo no encontrado en backend, se omite archivado: %s", key_actual)
        return

    sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    directorio = str(Path(key_actual).parent)
    extension  = Path(key_actual).suffix
    key_archivado = f"{directorio}/formulario_firmado_corregido_{sello}{extension}"
    storage.mover(key_actual, key_archivado)
    logger.info("Versión anterior archivada: %s → %s", key_actual, key_archivado)
