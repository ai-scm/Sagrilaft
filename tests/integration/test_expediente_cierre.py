import hashlib
import hmac
import json

import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.constantes import (
    CAUSAL_CIERRE_INFORME_FINAL,
    CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
    TIPO_DOCUMENTO_REPORTE_FINAL,
)
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import DocumentoAdjunto, EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _firma_hmac_zoho(cuerpo: bytes) -> str:
    return hmac.new(b"zoho-webhook-test", cuerpo, hashlib.sha256).hexdigest()


def _firmar_expediente(cliente_api, formulario_id: str) -> str:
    respuesta_aprobacion = cliente_api.post(f"/api/expedientes/{formulario_id}/aprobar")
    assert respuesta_aprobacion.status_code == 200, respuesta_aprobacion.text

    respuesta_firma = cliente_api.post(f"/api/expedientes/{formulario_id}/enviar-a-firma")
    assert respuesta_firma.status_code == 200, respuesta_firma.text
    request_id = respuesta_firma.json()["request_id"]

    payload = {
        "notifications": {"operation_type": "RequestCompleted"},
        "requests": {
            "request_id": request_id,
            "request_status": "Completed",
        },
    }
    cuerpo = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    respuesta_webhook = cliente_api.post(
        "/api/webhooks/zoho-sign",
        content=cuerpo,
        headers={
            "content-type": "application/json",
            "X-ZS-WEBHOOK-SIGNATURE": _firma_hmac_zoho(cuerpo),
        },
    )
    assert respuesta_webhook.status_code == 200, respuesta_webhook.text
    return request_id


def test_cerrar_expediente_con_reporte_final_guarda_evidencia_y_trazabilidad(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _firmar_expediente(cliente_api, acceso["formulario_id"])
    reporte_final = b"%PDF-1.4\n% informe final de cierre\n"
    justificacion = "Informe final aprobado por el area de cumplimiento."

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/reporte-final",
        data={
            "causal_cierre": CAUSAL_CIERRE_INFORME_FINAL,
            "justificacion": justificacion,
        },
        files={
            "archivo": (
                "informe_final.pdf",
                reporte_final,
                "application/pdf",
            )
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "estado": EstadoFormulario.CERRADO.value,
        "causal_cierre": CAUSAL_CIERRE_INFORME_FINAL,
        "reporte_final_cargado": True,
        "version_numero": 1,
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    reporte = (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_documento=TIPO_DOCUMENTO_REPORTE_FINAL,
            deleted_at=None,
        )
        .one()
    )
    evento_reporte = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.REPORTE_FINAL_CARGADO,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.CERRADO.value
    assert reporte.nombre_archivo == "informe_final.pdf"
    assert reporte.ruta_archivo.endswith("reportes_finales/informe_final.pdf")
    assert reporte.content_type == "application/pdf"
    assert reporte.tamano == len(reporte_final)
    assert reporte.hash_sha256 == hashlib.sha256(reporte_final).hexdigest()
    assert reporte.subido_por == "analista.integracion@blend360.com"
    assert reporte.version_numero == 1
    assert reporte.version_anterior_id is None
    assert dependencias_dobles["storage"].existe(reporte.ruta_archivo)
    assert evento_reporte.estado_anterior == EstadoFormulario.FIRMADO.value
    assert evento_reporte.estado_nuevo == EstadoFormulario.CERRADO.value
    assert evento_reporte.actor_id == "analista.integracion@blend360.com"
    assert evento_reporte.actor_tipo == ActorTipo.OPERADOR
    metadata = json.loads(evento_reporte.metadata_json)
    assert metadata == {
        "upload_method": "MANUAL",
        "upload_reason": justificacion,
        "version": 1,
        "causal_cierre": CAUSAL_CIERRE_INFORME_FINAL,
    }

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA,
        TipoAlerta.FORMULARIO_FIRMADO,
        TipoAlerta.REPORTE_FINAL_CARGADO,
    ]
    assert dependencias_dobles["alertas_portal"].eventos[-1]["detalle"] == (
        "Carga de reporte final"
    )

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.CERRADO.value
    assert detalle["causal_cierre"] == CAUSAL_CIERRE_INFORME_FINAL
    assert any(
        documento["id"] == reporte.id
        and documento["tipo_documento"] == TIPO_DOCUMENTO_REPORTE_FINAL
        for documento in detalle["documentos"]
    )

    respuesta_descarga = cliente_api.get(
        f"/api/expedientes/{acceso['formulario_id']}/documentos/{reporte.id}/descargar"
    )
    assert respuesta_descarga.status_code == 200, respuesta_descarga.text
    assert respuesta_descarga.content == reporte_final


def test_cerrar_expediente_sin_reporte_final_por_no_continuacion_dialogos(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _firmar_expediente(cliente_api, acceso["formulario_id"])
    justificacion = "La contraparte no continua los dialogos comerciales."

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/reporte-final",
        data={
            "causal_cierre": CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
            "justificacion": justificacion,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "estado": EstadoFormulario.CERRADO.value,
        "causal_cierre": CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
        "reporte_final_cargado": False,
        "version_numero": None,
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    reportes = (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_documento=TIPO_DOCUMENTO_REPORTE_FINAL,
            deleted_at=None,
        )
        .all()
    )
    evento_cierre = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.EXPEDIENTE_CERRADO,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.CERRADO.value
    assert reportes == []
    assert evento_cierre.estado_anterior == EstadoFormulario.FIRMADO.value
    assert evento_cierre.estado_nuevo == EstadoFormulario.CERRADO.value
    assert evento_cierre.actor_id == "analista.integracion@blend360.com"
    assert evento_cierre.actor_tipo == ActorTipo.OPERADOR
    assert json.loads(evento_cierre.metadata_json) == {
        "causal_cierre": CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
        "requiere_reporte_final": False,
        "justificacion": justificacion,
    }
    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA,
        TipoAlerta.FORMULARIO_FIRMADO,
    ]

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.CERRADO.value
    assert detalle["causal_cierre"] == CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS
    assert all(
        documento["tipo_documento"] != TIPO_DOCUMENTO_REPORTE_FINAL
        for documento in detalle["documentos"]
    )
