import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.constantes import TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT
from domain.excepciones import ZohoSignAutenticacionError, ZohoSignIndisponibleError
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import DocumentoAdjunto, EventoFormulario, Formulario
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _aprobar_expediente(cliente_api, formulario_id: str) -> None:
    respuesta = cliente_api.post(f"/api/expedientes/{formulario_id}/aprobar")
    assert respuesta.status_code == 200, respuesta.text


def test_enviar_expediente_validado_a_firma_crea_solicitud_zoho_y_trazabilidad(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _aprobar_expediente(cliente_api, acceso["formulario_id"])

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/enviar-a-firma"
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "request_id": "zoho-test-1",
        "estado": EstadoFormulario.PENDIENTE_FIRMA.value,
        "correo_firmante": acceso["correo_destinatario"],
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    evento_firma = (
        sesion_bd.query(EventoFormulario)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_evento=TipoEvento.FIRMA_INICIADA,
        )
        .one()
    )
    certificado = (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=acceso["formulario_id"],
            tipo_documento=TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
            deleted_at=None,
        )
        .one()
    )

    assert formulario.estado == EstadoFormulario.PENDIENTE_FIRMA.value
    assert formulario.zoho_request_id == "zoho-test-1"
    assert formulario.ruta_documento_firmado is None
    assert evento_firma.estado_anterior == EstadoFormulario.VALIDADO.value
    assert evento_firma.estado_nuevo == EstadoFormulario.PENDIENTE_FIRMA.value
    assert evento_firma.actor_id == "analista.integracion@blend360.com"
    assert evento_firma.actor_tipo == ActorTipo.OPERADOR
    assert certificado.nombre_archivo == "certificado_sagrilaft.pdf"
    assert certificado.subido_por == ActorTipo.SISTEMA
    assert certificado.tamano > 0
    assert certificado.hash_sha256

    solicitudes_zoho = dependencias_dobles["zoho_sign"].solicitudes_creadas
    assert len(solicitudes_zoho) == 1
    solicitud = solicitudes_zoho[0]
    assert len(solicitud["pdf_paths"]) == 2
    assert solicitud["nombre_documento"] == f"SAGRILAFT — {acceso['razon_social']}"
    assert solicitud["correo_firmante"] == acceso["correo_destinatario"]
    assert solicitud["nombre_firmante"] == "Representante Legal"

    assert [evento["tipo"] for evento in dependencias_dobles["alertas_portal"].eventos] == [
        TipoAlerta.FORMULARIO_RECIBIDO,
        TipoAlerta.FORMULARIO_ENVIADO_A_FIRMA,
    ]
    assert dependencias_dobles["alertas_portal"].eventos[-1]["formulario_id"] == acceso[
        "formulario_id"
    ]

    detalle = cliente_api.get(f"/api/expedientes/{acceso['formulario_id']}").json()
    assert detalle["estado"] == EstadoFormulario.PENDIENTE_FIRMA.value
    assert detalle["documento_firmado_disponible"] is False


def _certificados_activos(sesion_bd, formulario_id: str) -> list[DocumentoAdjunto]:
    return (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=formulario_id,
            tipo_documento=TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
            deleted_at=None,
        )
        .all()
    )


def test_falla_transitoria_de_zoho_responde_502_y_formulario_sigue_validado(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    """CA1 + CA3: agotados los reintentos por error transitorio, la respuesta
    ya no es un 500 generico -- es 502 con hint de reintentar -- y el
    formulario permanece en VALIDADO (no queda en un estado intermedio roto)."""
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _aprobar_expediente(cliente_api, acceso["formulario_id"])

    dependencias_dobles["zoho_sign"].proxima_llamada_falla_con = ZohoSignIndisponibleError(
        "ZohoSign no respondió con éxito tras 3 intentos (último HTTP 503)."
    )

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/enviar-a-firma"
    )

    assert respuesta.status_code == 502, respuesta.text
    cuerpo = respuesta.json()
    assert "reintente" in cuerpo["hint"].lower()

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    assert formulario.estado == EstadoFormulario.VALIDADO.value
    assert formulario.zoho_request_id is None
    assert len(_certificados_activos(sesion_bd, acceso["formulario_id"])) == 1


def test_falla_autenticacion_de_zoho_responde_502_con_hint_de_escalar(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    """CA2 + CA3: un error de autenticacion (401/403) responde con un hint
    distinto (escalar/revisar credenciales, no reintentar), y el formulario
    tambien permanece en VALIDADO."""
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _aprobar_expediente(cliente_api, acceso["formulario_id"])

    dependencias_dobles["zoho_sign"].proxima_llamada_falla_con = ZohoSignAutenticacionError(
        "ZohoSign rechazó las credenciales al refrescar el token (HTTP 401)."
    )

    respuesta = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/enviar-a-firma"
    )

    assert respuesta.status_code == 502, respuesta.text
    cuerpo = respuesta.json()
    assert "credencial" in cuerpo["hint"].lower()

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    assert formulario.estado == EstadoFormulario.VALIDADO.value


def test_reintento_exitoso_tras_falla_no_duplica_certificado(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    """CA4: tras una falla transitoria, un reintento exitoso no debe generar
    un segundo documento de certificado SAGRILAFT -- el existente se
    actualiza in-place (ver DocumentoService._registrar_certificado)."""
    acceso = radicar_formulario_juridico_con_documentos(cliente_api)
    _aprobar_expediente(cliente_api, acceso["formulario_id"])

    dependencias_dobles["zoho_sign"].proxima_llamada_falla_con = ZohoSignIndisponibleError(
        "falla simulada"
    )
    respuesta_fallida = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/enviar-a-firma"
    )
    assert respuesta_fallida.status_code == 502, respuesta_fallida.text

    # El flag de falla ya se limpió solo (ver ZohoSignEnMemoria) -- este
    # segundo intento debe tener éxito.
    respuesta_exitosa = cliente_api.post(
        f"/api/expedientes/{acceso['formulario_id']}/enviar-a-firma"
    )
    assert respuesta_exitosa.status_code == 200, respuesta_exitosa.text

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    assert formulario.estado == EstadoFormulario.PENDIENTE_FIRMA.value

    certificados = _certificados_activos(sesion_bd, acceso["formulario_id"])
    assert len(certificados) == 1, "el reintento no debe duplicar el certificado SAGRILAFT"
