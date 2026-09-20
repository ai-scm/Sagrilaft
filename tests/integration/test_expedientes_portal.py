import pytest

from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from soporte.accesos import crear_acceso_manual
from soporte.documentos import DOCUMENTOS_REQUERIDOS
from soporte.radicacion import radicar_formulario_juridico_con_documentos


pytestmark = pytest.mark.integration


def _listar_expedientes(cliente_api, **params):
    respuesta = cliente_api.get("/api/expedientes/", params=params)

    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _obtener_detalle_expediente(cliente_api, formulario_id: str):
    respuesta = cliente_api.get(f"/api/expedientes/{formulario_id}")

    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_portal_lista_detalla_y_descarga_expediente_radicado_con_documentos(cliente_api):
    acceso_borrador = crear_acceso_manual(
        cliente_api,
        razon_social="Proveedor Todavia Borrador SAS",
        correo_destinatario="borrador@proveedor.com",
    )
    acceso_radicado = radicar_formulario_juridico_con_documentos(cliente_api)

    expedientes = _listar_expedientes(cliente_api)

    assert [expediente["formulario_id"] for expediente in expedientes] == [
        acceso_radicado["formulario_id"]
    ]
    resumen = expedientes[0]
    assert resumen["formulario_id"] == acceso_radicado["formulario_id"]
    assert resumen["codigo_peticion"] == acceso_radicado["codigo_peticion"]
    assert resumen["razon_social"] == "Proveedor Integracion SAS"
    assert resumen["numero_identificacion"] == "900123456"
    assert resumen["tipo_contraparte"] == "proveedor"
    assert resumen["tipo_persona"] == "juridica"
    assert resumen["tipo_solicitud"] == "vinculacion"
    assert resumen["estado"] == EstadoFormulario.ENVIADO.value
    assert resumen["numero_correccion"] == 0
    assert resumen["cantidad_documentos"] == len(DOCUMENTOS_REQUERIDOS) + 1

    assert _listar_expedientes(cliente_api, tipo_contraparte="proveedor") == expedientes
    assert _listar_expedientes(cliente_api, tipo_contraparte="cliente") == []
    assert _listar_expedientes(cliente_api, busqueda="Integracion")[0]["formulario_id"] == acceso_radicado["formulario_id"]
    assert _listar_expedientes(cliente_api, busqueda=acceso_radicado["codigo_peticion"])[0]["formulario_id"] == acceso_radicado["formulario_id"]
    assert acceso_borrador["formulario_id"] not in {
        expediente["formulario_id"] for expediente in expedientes
    }

    detalle = _obtener_detalle_expediente(cliente_api, acceso_radicado["formulario_id"])

    assert detalle["formulario_id"] == acceso_radicado["formulario_id"]
    assert detalle["codigo_peticion"] == acceso_radicado["codigo_peticion"]
    assert detalle["razon_social"] == "Proveedor Integracion SAS"
    assert detalle["tipo_contraparte"] == "proveedor"
    assert detalle["tipo_persona"] == "juridica"
    assert detalle["tipo_solicitud"] == "vinculacion"
    assert detalle["estado"] == EstadoFormulario.ENVIADO.value
    assert detalle["numero_correccion"] == 0
    assert detalle["campos_a_corregir"] is None
    assert detalle["documento_firmado_disponible"] is False
    assert detalle["alertas_inconsistencia"] == []

    documentos = detalle["documentos"]
    assert {documento["tipo_documento"] for documento in documentos} == {
        *(tipo_documento for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS),
        TIPO_DOCUMENTO_FORMULARIO_PDF,
    }
    assert all(documento["id"] for documento in documentos)
    assert all(documento["nombre_archivo"].endswith(".pdf") for documento in documentos)
    assert all(documento["tamano"] > 0 for documento in documentos)
    assert all(documento["version_numero"] == 1 for documento in documentos)
    assert all(documento["created_at"] for documento in documentos)

    pdf_oficial = next(
        documento
        for documento in documentos
        if documento["tipo_documento"] == TIPO_DOCUMENTO_FORMULARIO_PDF
    )
    assert pdf_oficial["subido_por"] == "SISTEMA"

    respuesta_descarga = cliente_api.get(
        f"/api/expedientes/{acceso_radicado['formulario_id']}/documentos/{pdf_oficial['id']}/descargar"
    )

    assert respuesta_descarga.status_code == 200, respuesta_descarga.text
    assert respuesta_descarga.headers["content-type"] == "application/pdf"
    assert respuesta_descarga.content.startswith(b"%PDF")
