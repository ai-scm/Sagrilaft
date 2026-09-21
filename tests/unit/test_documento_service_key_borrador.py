"""
Regresión del bug de concurrencia encontrado en el load test del 2026-09-21
(ver docs/RUNBOOK_OPERATIVO.md sección 3): dos subidas con el mismo
codigo_peticion + nombre_archivo generaban la misma key de S3, y
`reemplazar_documento_anterior` podía borrar el archivo que otra petición
concurrente todavía estaba leyendo para Bedrock (500 NoSuchKey).
"""
import re

from services.formulario.documento_service import DocumentoService


def _service() -> DocumentoService:
    return DocumentoService(repo=None, storage=None)  # type: ignore[arg-type]


def test_key_borrador_es_unica_para_mismo_codigo_y_nombre_archivo():
    service = _service()

    key_1 = service.key_borrador("SAG-1", "rut.pdf")
    key_2 = service.key_borrador("SAG-1", "rut.pdf")

    assert key_1 != key_2, "dos subidas concurrentes no deben compartir la misma key en S3"


def test_key_borrador_mantiene_prefijo_tmp_y_nombre_legible():
    service = _service()

    key = service.key_borrador("SAG-1", "../rut inicial.pdf")

    assert key.startswith("tmp/SAG-1/")
    assert key.endswith("_rut_inicial.pdf")
    assert re.match(r"^tmp/SAG-1/[0-9a-f]{12}_rut_inicial\.pdf$", key)
