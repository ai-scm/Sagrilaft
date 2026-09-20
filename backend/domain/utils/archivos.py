"""
Lectura acotada de archivos subidos por el usuario.

UploadFile.read() sin límite carga el archivo completo a memoria como un solo
bytes object, sin importar cuánta RAM tenga el contenedor. Un archivo gigante
en una sola petición puede agotar la memoria del proceso (DoS de un solo tiro,
sin necesitar volumen de tráfico). Este helper lee en bloques y aborta apenas
se supera el límite, para no retener en memoria más que el límite configurado.
"""

from pathlib import Path

from fastapi import UploadFile

_TAMANO_BLOQUE = 1024 * 1024  # 1 MiB
_TIPOS_DOCUMENTO_DILIGENCIAMIENTO = {
    "cedula_representante": {
        "nombre": "Cédula del Representante Legal",
        "extensiones": {".pdf", ".jpg", ".jpeg", ".png"},
        "content_types": {"application/pdf", "image/jpeg", "image/png"},
    },
    "certificado_existencia": {
        "nombre": "Certificado de Existencia y Representación Legal",
        "extensiones": {".pdf"},
        "content_types": {"application/pdf"},
    },
    "estados_financieros": {
        "nombre": "Estados Financieros",
        "extensiones": {".pdf"},
        "content_types": {"application/pdf"},
    },
    "declaracion_renta": {
        "nombre": "Declaración de Renta",
        "extensiones": {".pdf"},
        "content_types": {"application/pdf"},
    },
    "rut": {
        "nombre": "RUT (Registro Único Tributario)",
        "extensiones": {".pdf"},
        "content_types": {"application/pdf"},
    },
    "referencias_bancarias": {
        "nombre": "Referencias Bancarias",
        "extensiones": {".pdf"},
        "content_types": {"application/pdf"},
    },
}


class ArchivoDemasiadoGrandeError(Exception):
    def __init__(self, max_mb: int):
        self.max_mb = max_mb
        super().__init__(f"El archivo supera el límite permitido de {max_mb} MB.")


class TipoDocumentoNoPermitidoError(Exception):
    def __init__(self, tipo_documento: str):
        self.tipo_documento = tipo_documento
        super().__init__(f"Tipo de documento no permitido: '{tipo_documento}'.")


class ArchivoDocumentoInvalidoError(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)


def tipos_documento_diligenciamiento() -> tuple[str, ...]:
    return tuple(_TIPOS_DOCUMENTO_DILIGENCIAMIENTO)


def documentos_diligenciamiento_requeridos() -> tuple[str, ...]:
    return tipos_documento_diligenciamiento()


def nombre_documento_diligenciamiento(tipo_documento: str) -> str:
    reglas = _TIPOS_DOCUMENTO_DILIGENCIAMIENTO.get(tipo_documento)
    if not reglas:
        return tipo_documento
    return str(reglas["nombre"])


def validar_archivo_diligenciamiento(
    *,
    tipo_documento: str,
    nombre_archivo: str,
    content_type: str | None,
) -> None:
    reglas = _TIPOS_DOCUMENTO_DILIGENCIAMIENTO.get(tipo_documento)
    if not reglas:
        raise TipoDocumentoNoPermitidoError(tipo_documento)

    extension = Path(nombre_archivo).suffix.lower()
    if extension not in reglas["extensiones"]:
        extensiones = ", ".join(sorted(reglas["extensiones"]))
        raise ArchivoDocumentoInvalidoError(
            f"Extensión no permitida para '{tipo_documento}'. Use: {extensiones}."
        )

    if content_type not in reglas["content_types"]:
        raise ArchivoDocumentoInvalidoError(
            f"Tipo de archivo no permitido para '{tipo_documento}'."
        )


async def leer_archivo_limitado(archivo: UploadFile, max_mb: int) -> bytes:
    max_bytes = max_mb * 1024 * 1024
    bloques: list[bytes] = []
    total = 0

    while True:
        bloque = await archivo.read(_TAMANO_BLOQUE)
        if not bloque:
            break
        total += len(bloque)
        if total > max_bytes:
            raise ArchivoDemasiadoGrandeError(max_mb)
        bloques.append(bloque)

    return b"".join(bloques)
