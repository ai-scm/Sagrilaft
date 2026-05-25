"""
Operaciones de almacenamiento en disco para el flujo de firma electrónica.

Funciones puras de rutas y filesystem — sin dependencias de DB ni servicios.
Paralelas en responsabilidad a almacenamiento_contraparte.py.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from domain.formulario.entidades import FormularioDatos
from services.formulario.almacenamiento_contraparte import resolver_ruta_contraparte

logger = logging.getLogger(__name__)

_NOMBRE_PDF_FIRMADO     = "formulario_firmado.pdf"
_NOMBRE_PDF_CERTIFICADO = "certificado_sagrilaft.pdf"


def resolver_ruta_certificado(pdf_formulario: Path) -> Path:
    """Devuelve la ruta del certificado SAGRILAFT junto al PDF del formulario."""
    return pdf_formulario.parent / _NOMBRE_PDF_CERTIFICADO


def resolver_ruta_documento_firmado(formulario: FormularioDatos, upload_dir: Path) -> Path:
    """Devuelve la ruta en disco donde se guarda el PDF firmado del formulario."""
    directorio_contraparte = resolver_ruta_contraparte(
        tipo_contraparte=formulario.tipo_contraparte or "",
        razon_social=formulario.razon_social or "",
        upload_dir=upload_dir,
    )
    return directorio_contraparte / _NOMBRE_PDF_FIRMADO


def archivar_version_anterior(ruta_version_actual: Path) -> None:
    """
    Renombra el documento firmado existente añadiendo un sello de fecha/hora
    antes de guardar una nueva versión corregida.

    Convención:  formulario_firmado_corregido_YYYYMMDD_HHMMSS.pdf
    Si el archivo no existe en disco (ruta obsoleta de una migración anterior)
    el archivado se omite sin error.
    """
    if not ruta_version_actual.exists():
        logger.warning(
            "Archivo previo no encontrado en disco, se omite el archivado: %s",
            ruta_version_actual,
        )
        return

    sello_temporal = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    nombre_archivado = f"formulario_firmado_corregido_{sello_temporal}.pdf"
    ruta_archivada = ruta_version_actual.parent / nombre_archivado
    ruta_version_actual.rename(ruta_archivada)

    logger.info(
        "Versión anterior archivada: %s → %s",
        ruta_version_actual.name,
        ruta_archivada.name,
    )
