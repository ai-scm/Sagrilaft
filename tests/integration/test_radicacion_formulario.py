import pytest

from domain.auditoria.entidades import ActorTipo, TipoEvento
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.persistencia.models import (
    AccesoManual,
    DocumentoAdjunto,
    EventoFormulario,
    Formulario,
)
from soporte.accesos import crear_acceso_manual
from soporte.documentos import subir_documentos_requeridos
from soporte.formularios import (
    formulario_minimo_juridica_para_envio,
    formulario_minimo_natural_para_envio,
)


pytestmark = pytest.mark.integration


def _autoguardar_formulario(cliente_api, formulario_id, datos_formulario):
    respuesta = cliente_api.put(f"/api/formularios/{formulario_id}", json=datos_formulario)

    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _enviar_formulario(cliente_api, acceso):
    respuesta = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": acceso["token_diligenciamiento"],
            },
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    resultado = respuesta.json()
    assert resultado["valido"] is True
    assert resultado["errores"] == []
    return resultado


def _obtener_unico(modelo, sesion_bd, **filtros):
    return sesion_bd.query(modelo).filter_by(**filtros).one()


def _assert_formulario_radicado(sesion_bd, formulario_id):
    formulario = _obtener_unico(Formulario, sesion_bd, id=formulario_id)
    assert formulario.estado == EstadoFormulario.ENVIADO.value


def _assert_acceso_consumido(sesion_bd, formulario_id):
    acceso = _obtener_unico(AccesoManual, sesion_bd, formulario_id=formulario_id)
    assert acceso.consumed_at is not None


def _assert_pdf_oficial_generado(sesion_bd, storage, formulario_id):
    documento = _obtener_unico(
        DocumentoAdjunto,
        sesion_bd,
        formulario_id=formulario_id,
        tipo_documento=TIPO_DOCUMENTO_FORMULARIO_PDF,
        deleted_at=None,
    )

    assert documento.nombre_archivo.endswith(".pdf")
    assert documento.content_type == "application/pdf"
    assert documento.subido_por == "SISTEMA"
    assert documento.version_numero == 1
    assert documento.tamano > 0
    assert documento.hash_sha256
    assert documento.snapshot_datos
    assert storage.existe(documento.ruta_archivo)


def _assert_auditoria_de_radicacion(sesion_bd, formulario_id, actor_id):
    evento = _obtener_unico(
        EventoFormulario,
        sesion_bd,
        formulario_id=formulario_id,
        tipo_evento=TipoEvento.FORMULARIO_ENVIADO,
    )

    assert evento.estado_anterior == EstadoFormulario.BORRADOR.value
    assert evento.estado_nuevo == EstadoFormulario.ENVIADO.value
    assert evento.actor_id == actor_id
    assert evento.actor_tipo == ActorTipo.CONTRAPARTE


def _assert_alerta_formulario_recibido(alertas_portal, formulario_id):
    assert len(alertas_portal.eventos) == 1
    alerta = alertas_portal.eventos[0]
    assert alerta["tipo"] == TipoAlerta.FORMULARIO_RECIBIDO
    assert alerta["formulario_id"] == formulario_id
    assert alerta["razon_social"] == "Proveedor Integracion SAS"
    assert alerta["tipo_contraparte"] == "proveedor"


def _assert_acceso_bloqueado_despues_de_radicacion(cliente_api, acceso):
    respuesta_token = cliente_api.get(
        f"/api/accesos-manuales/token/{acceso['token_diligenciamiento']}"
    )
    assert respuesta_token.status_code == 410, respuesta_token.text

    respuesta_recuperacion = cliente_api.post(
        "/api/formularios/sesion/recuperar-por-acceso",
        json={
            "codigo_peticion": acceso["codigo_peticion"],
            "pin": acceso["pin"],
        },
    )
    assert respuesta_recuperacion.status_code == 409, respuesta_recuperacion.text

    respuesta_listado = cliente_api.get("/api/accesos-manuales/")
    assert respuesta_listado.status_code == 200, respuesta_listado.text
    acceso_listado = next(
        item
        for item in respuesta_listado.json()
        if item["formulario_id"] == acceso["formulario_id"]
    )
    assert acceso_listado["estado_acceso"] == "consumido"
    assert acceso_listado["consumed_at"] is not None


def test_persona_juridica_radica_con_documentos_requeridos(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)

    _autoguardar_formulario(
        cliente_api,
        acceso["formulario_id"],
        formulario_minimo_juridica_para_envio(),
    )
    subir_documentos_requeridos(cliente_api, acceso["formulario_id"])
    _enviar_formulario(cliente_api, acceso)

    _assert_formulario_radicado(sesion_bd, acceso["formulario_id"])
    _assert_acceso_consumido(sesion_bd, acceso["formulario_id"])
    _assert_pdf_oficial_generado(
        sesion_bd,
        dependencias_dobles["storage"],
        acceso["formulario_id"],
    )
    _assert_auditoria_de_radicacion(
        sesion_bd,
        acceso["formulario_id"],
        actor_id=acceso["correo_destinatario"],
    )
    _assert_alerta_formulario_recibido(
        dependencias_dobles["alertas_portal"],
        acceso["formulario_id"],
    )
    _assert_acceso_bloqueado_despues_de_radicacion(cliente_api, acceso)


def test_persona_natural_radica_con_documentos_requeridos(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    datos_formulario = formulario_minimo_natural_para_envio(
        junta_directiva=[
            {
                "cargo": "Representante Legal",
                "nombre": "Dato no aplicable",
                "tipo_id": "CC",
                "numero_id": "90909090",
                "es_pep": "no",
            }
        ],
        accionistas=[
            {
                "nombre": "Dato no aplicable",
                "tipo_id": "CC",
                "numero_id": "80808080",
                "es_pep": "no",
                "porcentaje": 60,
            }
        ],
        beneficiario_final=[
            {
                "nombre": "Dato no aplicable",
                "tipo_id": "CC",
                "numero_id": "70707070",
                "es_pep": "no",
                "porcentaje": 60,
            }
        ],
    )

    formulario_guardado = _autoguardar_formulario(
        cliente_api,
        acceso["formulario_id"],
        datos_formulario,
    )

    assert formulario_guardado["tipo_persona"] == "natural"
    assert formulario_guardado["direccion_residencia"] == "Carrera 15 90 10"
    assert formulario_guardado["ciudad_residencia"] == "Bogota"
    assert formulario_guardado["junta_directiva"] == []
    assert formulario_guardado["accionistas"] == []
    assert formulario_guardado["beneficiario_final"] == []
    assert formulario_guardado["actividad_clasificacion"] is None
    assert formulario_guardado["regimen_iva"] is None

    subir_documentos_requeridos(cliente_api, acceso["formulario_id"])
    _enviar_formulario(cliente_api, acceso)

    _assert_formulario_radicado(sesion_bd, acceso["formulario_id"])
    _assert_acceso_consumido(sesion_bd, acceso["formulario_id"])
    _assert_pdf_oficial_generado(
        sesion_bd,
        dependencias_dobles["storage"],
        acceso["formulario_id"],
    )
    _assert_auditoria_de_radicacion(
        sesion_bd,
        acceso["formulario_id"],
        actor_id=acceso["correo_destinatario"],
    )
    _assert_alerta_formulario_recibido(
        dependencias_dobles["alertas_portal"],
        acceso["formulario_id"],
    )
    _assert_acceso_bloqueado_despues_de_radicacion(cliente_api, acceso)
