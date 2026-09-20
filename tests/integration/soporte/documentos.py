TIPO_DOCUMENTO_RUT = "rut"

DOCUMENTOS_REQUERIDOS = [
    ("cedula_representante", "cedula_representante.pdf", "application/pdf"),
    ("certificado_existencia", "certificado_existencia.pdf", "application/pdf"),
    ("estados_financieros", "estados_financieros.pdf", "application/pdf"),
    ("declaracion_renta", "declaracion_renta.pdf", "application/pdf"),
    (TIPO_DOCUMENTO_RUT, "rut.pdf", "application/pdf"),
    ("referencias_bancarias", "referencias_bancarias.pdf", "application/pdf"),
]


def contenido_documento(tipo_documento: str) -> bytes:
    return f"%PDF-1.4\n{tipo_documento} de prueba\n".encode("utf-8")


def subir_documento(
    cliente_api,
    formulario_id: str,
    *,
    tipo_documento: str = TIPO_DOCUMENTO_RUT,
    nombre_archivo: str = "rut.pdf",
    contenido: bytes = b"%PDF-1.4\nrut de prueba\n",
    content_type: str = "application/pdf",
) -> dict:
    respuesta = cliente_api.post(
        f"/api/formularios/{formulario_id}/documentos",
        data={"tipo_documento": tipo_documento},
        files={"archivo": (nombre_archivo, contenido, content_type)},
    )

    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def intentar_subir_documento(
    cliente_api,
    formulario_id: str,
    *,
    tipo_documento: str,
    nombre_archivo: str,
    contenido: bytes = b"%PDF-1.4\narchivo de prueba\n",
    content_type: str = "application/pdf",
):
    return cliente_api.post(
        f"/api/formularios/{formulario_id}/documentos",
        data={"tipo_documento": tipo_documento},
        files={"archivo": (nombre_archivo, contenido, content_type)},
    )


def subir_documentos_requeridos(
    cliente_api,
    formulario_id: str,
    *,
    omitir: set[str] | str | None = None,
) -> None:
    omitidos = {omitir} if isinstance(omitir, str) else set(omitir or [])
    for tipo_documento, nombre_archivo, content_type in DOCUMENTOS_REQUERIDOS:
        if tipo_documento in omitidos:
            continue
        subir_documento(
            cliente_api,
            formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            contenido=contenido_documento(tipo_documento),
            content_type=content_type,
        )
