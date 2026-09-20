import json

import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import AccesoManual, DocumentoAdjunto, EventoFormulario, Formulario
from soporte.formularios import formulario_minimo_juridica_para_envio
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _devolver_para_correccion(cliente_api, acceso: dict) -> str:
    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/devolver",
        json={
            "especificaciones": "Corregir el telefono de contacto antes de reenviar.",
            "campos_identificados": ["telefono"],
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["estado"]


def _acceso_en_bd(sesion_bd, formulario_id: str) -> AccesoManual:
    return sesion_bd.query(AccesoManual).filter_by(formulario_id=formulario_id).one()


def _documentos_pdf_formulario(sesion_bd, formulario_id: str) -> list[DocumentoAdjunto]:
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


def test_reenviar_correccion_genera_nueva_version_y_alerta_formulario_corregido(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    sesion_bd.expire_all()
    pdf_inicial = _documentos_pdf_formulario(sesion_bd, acceso["formulario_id"])[0]

    assert _devolver_para_correccion(cliente_api, acceso) == EstadoFormulario.EN_CORRECCION.value

    sesion_bd.expire_all()
    acceso_reactivado = _acceso_en_bd(sesion_bd, acceso["formulario_id"])
    token_correccion = acceso_reactivado.token_diligenciamiento

    respuesta_token = cliente_api.get(f"/api/accesos-manuales/token/{token_correccion}")
    assert respuesta_token.status_code == 200, respuesta_token.text
    assert respuesta_token.json()["estado"] == EstadoFormulario.EN_CORRECCION.value

    datos_corregidos = formulario_minimo_juridica_para_envio(
        telefono="6015559999",
        pagina_actual=8,
    )
    respuesta_guardado = cliente_api.put(
        f"/api/formularios/{acceso['formulario_id']}",
        json=datos_corregidos,
    )
    assert respuesta_guardado.status_code == 200, respuesta_guardado.text
    assert respuesta_guardado.json()["telefono"] == "6015559999"

    respuesta_reenvio = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": token_correccion,
            },
        },
    )

    assert respuesta_reenvio.status_code == 200, respuesta_reenvio.text
    assert respuesta_reenvio.json() == {"valido": True, "errores": []}

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_consumido = _acceso_en_bd(sesion_bd, acceso["formulario_id"])
    eventos_reenvio = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FORMULARIO_ENVIADO,
        )
        .order_by(EventoFormulario.id.asc())
        .all()
    )
    pdfs_formulario = _documentos_pdf_formulario(sesion_bd, acceso["formulario_id"])

    assert formulario.estado == EstadoFormulario.ENVIADO.value
    assert formulario.telefono == "6015559999"
    assert formulario.numero_correccion == 1
    assert json.loads(formulario.campos_a_corregir)["campos"] == ["telefono"]
    assert acceso_consumido.consumed_at is not None
    assert acceso_consumido.token_diligenciamiento == token_correccion
    assert len(eventos_reenvio) == 2
    assert eventos_reenvio[-1].estado_anterior == EstadoFormulario.EN_CORRECCION.value
    assert eventos_reenvio[-1].estado_nuevo == EstadoFormulario.ENVIADO.value
    assert eventos_reenvio[-1].actor_id == acceso["correo_destinatario"]
    assert eventos_reenvio[-1].actor_tipo == ActorTipo.CONTRAPARTE
    assert [pdf.version_numero for pdf in pdfs_formulario] == [1, 2]
    assert pdfs_formulario[1].version_anterior_id == pdf_inicial.id
    assert json.loads(pdfs_formulario[1].snapshot_datos)["telefono"] == "6015559999"
    assert dependencias_dobles["storage"].existe(pdfs_formulario[1].ruta_archivo)

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_DEVUELTO,
        TipoAlerta.FORMULARIO_CORREGIDO,
    ]
    alerta_corregido = dependencias_dobles["alertas_portal"].eventos[-1]
    assert alerta_corregido["formulario_id"] == acceso["formulario_id"]
    assert alerta_corregido["razon_social"] == "Proveedor Integracion SAS"

    respuesta_token_consumido = cliente_api.get(f"/api/accesos-manuales/token/{token_correccion}")
    assert respuesta_token_consumido.status_code == 410, respuesta_token_consumido.text

    respuesta_detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}")
    assert respuesta_detalle.status_code == 200, respuesta_detalle.text
    detalle = respuesta_detalle.json()
    assert detalle["estado"] == EstadoFormulario.ENVIADO.value
    assert detalle["modo_trabajo"] == ""
    assert {
        documento["version_numero"]
        for documento in detalle["documentos"]
        if documento["tipo_documento"] == TIPO_DOCUMENTO_FORMULARIO_PDF
    } == {1, 2}
