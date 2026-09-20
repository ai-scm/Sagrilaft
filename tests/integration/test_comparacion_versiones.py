import json

import pytest

from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from infrastructure.persistencia.models import AccesoManual, DocumentoAdjunto
from soporte.formularios import formulario_minimo_juridica_para_envio
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _devolver_para_correccion(cliente_api, formulario_id: str) -> None:
    respuesta = cliente_api.post(
        f"/api/expedientes/{formulario_id}/devolver",
        json={
            "especificaciones": "Corregir el telefono de contacto antes de reenviar.",
            "campos_identificados": ["telefono"],
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == EstadoFormulario.EN_CORRECCION.value


def _token_correccion(sesion_bd, formulario_id: str) -> str:
    acceso = sesion_bd.query(AccesoManual).filter_by(formulario_id=formulario_id).one()
    return acceso.token_diligenciamiento


def _pdfs_formulario(sesion_bd, formulario_id: str) -> list[DocumentoAdjunto]:
    return (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=formulario_id,
            tipo_documento=TIPO_DOCUMENTO_FORMULARIO_PDF,
            deleted_at=None,
        )
        .order_by(DocumentoAdjunto.version_numero.asc())
        .all()
    )


def _reenviar_correccion_con_telefono(
    cliente_api,
    formulario_id: str,
    token_correccion: str,
    telefono: str,
    correo: str,
) -> None:
    respuesta_guardado = cliente_api.put(
        f"/api/formularios/{formulario_id}",
        json=formulario_minimo_juridica_para_envio(
            telefono=telefono,
            correo=correo,
            correo_representante=correo,
        ),
    )
    assert respuesta_guardado.status_code == 200, respuesta_guardado.text

    respuesta_reenvio = cliente_api.post(
        f"/api/formularios/{formulario_id}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": token_correccion,
            },
        },
    )
    assert respuesta_reenvio.status_code == 200, respuesta_reenvio.text


def test_comparacion_versiones_detecta_cambio_y_genera_reporte_pdf(
    cliente_api,
    sesion_bd,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    formulario_id = acceso["formulario_id"]

    _devolver_para_correccion(cliente_api, formulario_id)
    sesion_bd.expire_all()
    token_correccion = _token_correccion(sesion_bd, formulario_id)

    _reenviar_correccion_con_telefono(
        cliente_api,
        formulario_id,
        token_correccion,
        telefono="6015559999",
        correo=acceso["correo_destinatario"],
    )

    sesion_bd.expire_all()
    pdf_inicial, pdf_corregido = _pdfs_formulario(sesion_bd, formulario_id)
    assert pdf_corregido.version_anterior_id == pdf_inicial.id
    assert json.loads(pdf_inicial.snapshot_datos)["telefono"] == "6015550101"
    assert json.loads(pdf_corregido.snapshot_datos)["telefono"] == "6015559999"

    respuesta = cliente_api.get(f"/api/expedientes/{formulario_id}/comparacion-versiones")

    assert respuesta.status_code == 200, respuesta.text
    comparacion = respuesta.json()
    assert comparacion["disponible"] is True
    assert comparacion["motivo"] is None
    assert comparacion["version_anterior"] == 1
    assert comparacion["version_corregida"] == 2
    assert comparacion["documento_anterior_id"] == pdf_inicial.id
    assert comparacion["documento_corregido_id"] == pdf_corregido.id
    assert comparacion["total_cambios"] == 1, comparacion["cambios"]
    assert comparacion["cambios"] == [
        {
            "campo": "telefono",
            "etiqueta": "Teléfono",
            "valor_anterior": "6015550101",
            "valor_corregido": "6015559999",
        }
    ]
    assert "telefono" not in comparacion["campos_complejos"]

    respuesta_especifica = cliente_api.get(
        f"/api/expedientes/{formulario_id}/comparacion-versiones-especificas",
        params={
            "base_id": pdf_inicial.id,
            "comparar_id": pdf_corregido.id,
        },
    )
    assert respuesta_especifica.status_code == 200, respuesta_especifica.text
    assert respuesta_especifica.json()["cambios"] == comparacion["cambios"]

    respuesta_reporte = cliente_api.get(
        f"/api/expedientes/{formulario_id}/comparacion-versiones/reporte-pdf"
    )
    assert respuesta_reporte.status_code == 200, respuesta_reporte.text
    assert respuesta_reporte.headers["content-type"] == "application/pdf"
    assert respuesta_reporte.content.startswith(b"%PDF")
