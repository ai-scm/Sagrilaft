import hashlib

import pytest

from api.routers.formulario import obtener_max_upload_mb
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from infrastructure.persistencia.models import (
    AccesoManual,
    DocumentoAdjunto,
    EventoFormulario,
    Formulario,
)
from main import app as aplicacion_sagrilaft
from soporte.accesos import crear_acceso_manual
from soporte.documentos import (
    DOCUMENTOS_REQUERIDOS,
    TIPO_DOCUMENTO_RUT,
    contenido_documento,
    intentar_subir_documento,
    subir_documento,
    subir_documentos_requeridos,
)
from soporte.formularios import formulario_minimo_juridica_para_envio


pytestmark = pytest.mark.integration


def _autoguardar_formulario_completo(cliente_api, formulario_id: str) -> None:
    respuesta = cliente_api.put(
        f"/api/formularios/{formulario_id}",
        json=formulario_minimo_juridica_para_envio(),
    )

    assert respuesta.status_code == 200, respuesta.text


def _enviar_formulario(cliente_api, acceso: dict) -> None:
    respuesta = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": acceso["token_diligenciamiento"],
            },
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["valido"] is True


def _documentos_en_bd(sesion_bd, formulario_id: str) -> list[DocumentoAdjunto]:
    return (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(formulario_id=formulario_id)
        .order_by(DocumentoAdjunto.version_numero.asc(), DocumentoAdjunto.created_at.asc())
        .all()
    )


def _documento_activo_en_bd(
    sesion_bd,
    formulario_id: str,
    tipo_documento: str,
) -> DocumentoAdjunto:
    return (
        sesion_bd.query(DocumentoAdjunto)
        .filter_by(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            deleted_at=None,
        )
        .one()
    )


def test_carga_documento_registra_evidencia_en_bd_storage_e_ia(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    contenido = b"%PDF-1.4\nrut inicial\n"

    documento = subir_documento(
        cliente_api,
        acceso["formulario_id"],
        nombre_archivo="../rut inicial.pdf",
        contenido=contenido,
    )

    assert documento["tipo_documento"] == TIPO_DOCUMENTO_RUT
    assert documento["nombre_archivo"] == "rut_inicial.pdf"
    assert documento["content_type"] == "application/pdf"
    assert documento["tamano"] == len(contenido)
    assert documento["extraccion_exitosa"] is False
    assert documento["mensaje_extraccion"] == "Extracción IA omitida en pruebas de integración."

    documento_bd = _documento_activo_en_bd(
        sesion_bd,
        acceso["formulario_id"],
        TIPO_DOCUMENTO_RUT,
    )
    assert documento_bd.nombre_archivo == "rut_inicial.pdf"
    assert documento_bd.ruta_archivo == f"tmp/{acceso['codigo_peticion']}/rut_inicial.pdf"
    assert documento_bd.version_numero == 1
    assert documento_bd.version_anterior_id is None
    assert documento_bd.hash_sha256 == hashlib.sha256(contenido).hexdigest()
    assert documento_bd.subido_por == "CONTRAPARTE"
    assert documento_bd.tamano == len(contenido)
    assert dependencias_dobles["storage"].existe(documento_bd.ruta_archivo)

    extractor_ia = dependencias_dobles["extractor_ia"]
    assert extractor_ia.solicitudes == [
        {
            "ruta_archivo": str(
                dependencias_dobles["storage"].ruta_local(documento_bd.ruta_archivo)
            ),
            "tipo_documento": TIPO_DOCUMENTO_RUT,
        }
    ]

    respuesta_listado = cliente_api.get(
        f"/api/formularios/{acceso['formulario_id']}/documentos"
    )
    assert respuesta_listado.status_code == 200, respuesta_listado.text
    documentos = respuesta_listado.json()
    assert [item["id"] for item in documentos] == [documento_bd.id]


def test_reemplazo_y_radicacion_mueven_documento_a_carpeta_definitiva(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    storage = dependencias_dobles["storage"]

    subir_documentos_requeridos(
        cliente_api,
        acceso["formulario_id"],
        omitir=TIPO_DOCUMENTO_RUT,
    )

    primer_documento = subir_documento(
        cliente_api,
        acceso["formulario_id"],
        nombre_archivo="rut anterior.pdf",
        contenido=b"%PDF-1.4\nrut anterior\n",
    )
    segundo_contenido = b"%PDF-1.4\nrut vigente\n"

    segundo_documento = subir_documento(
        cliente_api,
        acceso["formulario_id"],
        nombre_archivo="rut vigente.pdf",
        contenido=segundo_contenido,
    )

    documentos_bd = _documentos_en_bd(sesion_bd, acceso["formulario_id"])
    documento_anterior = next(doc for doc in documentos_bd if doc.id == primer_documento["id"])
    documento_vigente = next(doc for doc in documentos_bd if doc.id == segundo_documento["id"])

    assert documento_anterior.version_numero == 1
    assert documento_anterior.deleted_at is not None
    assert storage.existe(documento_anterior.ruta_archivo) is False
    assert documento_vigente.version_numero == 2
    assert documento_vigente.version_anterior_id == documento_anterior.id
    assert documento_vigente.deleted_at is None
    assert documento_vigente.hash_sha256 == hashlib.sha256(segundo_contenido).hexdigest()
    assert documento_vigente.ruta_archivo == f"tmp/{acceso['codigo_peticion']}/rut_vigente.pdf"
    assert storage.existe(documento_vigente.ruta_archivo)

    respuesta_listado = cliente_api.get(
        f"/api/formularios/{acceso['formulario_id']}/documentos"
    )
    assert respuesta_listado.status_code == 200, respuesta_listado.text
    documentos_activos = respuesta_listado.json()
    documentos_rut = [
        documento
        for documento in documentos_activos
        if documento["tipo_documento"] == TIPO_DOCUMENTO_RUT
    ]
    assert [documento["id"] for documento in documentos_rut] == [documento_vigente.id]
    assert {
        documento["tipo_documento"] for documento in documentos_activos
    } == {tipo_documento for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS}

    _autoguardar_formulario_completo(cliente_api, acceso["formulario_id"])
    _enviar_formulario(cliente_api, acceso)

    sesion_bd.expire_all()
    documento_radicado = _documento_activo_en_bd(
        sesion_bd,
        acceso["formulario_id"],
        TIPO_DOCUMENTO_RUT,
    )
    pdf_oficial = _documento_activo_en_bd(
        sesion_bd,
        acceso["formulario_id"],
        TIPO_DOCUMENTO_FORMULARIO_PDF,
    )

    assert documento_radicado.id == documento_vigente.id
    assert documento_radicado.ruta_archivo == "PROVEEDORES/Proveedor Integracion SAS/rut_vigente.pdf"
    assert storage.existe(f"tmp/{acceso['codigo_peticion']}/rut_vigente.pdf") is False
    assert storage.existe(documento_radicado.ruta_archivo)
    assert pdf_oficial.ruta_archivo.startswith("PROVEEDORES/Proveedor Integracion SAS/")
    assert storage.existe(pdf_oficial.ruta_archivo)
    assert len(dependencias_dobles["extractor_ia"].solicitudes) == (
        len(DOCUMENTOS_REQUERIDOS) + 1
    )


def test_ciclo_documental_con_los_seis_documentos_requeridos(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    storage = dependencias_dobles["storage"]

    documentos_subidos = [
        subir_documento(
            cliente_api,
            acceso["formulario_id"],
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            contenido=contenido_documento(tipo_documento),
            content_type=content_type,
        )
        for tipo_documento, nombre_archivo, content_type in DOCUMENTOS_REQUERIDOS
    ]

    documentos_activos = {
        documento.tipo_documento: documento
        for documento in sesion_bd.query(DocumentoAdjunto)
        .filter_by(formulario_id=acceso["formulario_id"], deleted_at=None)
        .all()
    }
    assert set(documentos_activos) == {
        tipo_documento for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS
    }

    for tipo_documento, nombre_archivo, content_type in DOCUMENTOS_REQUERIDOS:
        documento = documentos_activos[tipo_documento]
        contenido = contenido_documento(tipo_documento)
        assert documento.formulario_id == acceso["formulario_id"]
        assert documento.nombre_archivo == nombre_archivo
        assert documento.content_type == content_type
        assert documento.tamano == len(contenido)
        assert documento.hash_sha256 == hashlib.sha256(contenido).hexdigest()
        assert documento.subido_por == "CONTRAPARTE"
        assert documento.version_numero == 1
        assert documento.version_anterior_id is None
        assert documento.ruta_archivo == f"tmp/{acceso['codigo_peticion']}/{nombre_archivo}"
        assert storage.existe(documento.ruta_archivo)

    respuesta_listado = cliente_api.get(
        f"/api/formularios/{acceso['formulario_id']}/documentos"
    )
    assert respuesta_listado.status_code == 200, respuesta_listado.text
    assert {
        documento["tipo_documento"] for documento in respuesta_listado.json()
    } == {tipo_documento for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS}

    assert [
        solicitud["tipo_documento"]
        for solicitud in dependencias_dobles["extractor_ia"].solicitudes
    ] == [tipo_documento for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS]

    _autoguardar_formulario_completo(cliente_api, acceso["formulario_id"])
    _enviar_formulario(cliente_api, acceso)

    sesion_bd.expire_all()
    documentos_radicados = {
        documento.tipo_documento: documento
        for documento in sesion_bd.query(DocumentoAdjunto)
        .filter_by(formulario_id=acceso["formulario_id"], deleted_at=None)
        .all()
    }

    for tipo_documento, nombre_archivo, _ in DOCUMENTOS_REQUERIDOS:
        documento = documentos_radicados[tipo_documento]
        ruta_temporal = f"tmp/{acceso['codigo_peticion']}/{nombre_archivo}"
        ruta_definitiva = f"PROVEEDORES/Proveedor Integracion SAS/{nombre_archivo}"
        assert documento.formulario_id == acceso["formulario_id"]
        assert documento.ruta_archivo == ruta_definitiva
        assert storage.existe(ruta_temporal) is False
        assert storage.existe(ruta_definitiva)

    assert _documento_activo_en_bd(
        sesion_bd,
        acceso["formulario_id"],
        TIPO_DOCUMENTO_FORMULARIO_PDF,
    )
    assert len(documentos_subidos) == len(DOCUMENTOS_REQUERIDOS)


def test_radicacion_rechaza_si_no_hay_documentos_e_indica_los_seis_faltantes(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)

    _autoguardar_formulario_completo(cliente_api, acceso["formulario_id"])
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
    assert resultado["valido"] is False
    assert [error["campo"] for error in resultado["errores"]] == [
        f"documentos.{tipo_documento}"
        for tipo_documento, _, _ in DOCUMENTOS_REQUERIDOS
    ]
    assert [error["mensaje"] for error in resultado["errores"]] == [
        "Debe cargar el documento obligatorio: Cédula del Representante Legal.",
        "Debe cargar el documento obligatorio: Certificado de Existencia y Representación Legal.",
        "Debe cargar el documento obligatorio: Estados Financieros.",
        "Debe cargar el documento obligatorio: Declaración de Renta.",
        "Debe cargar el documento obligatorio: RUT (Registro Único Tributario).",
        "Debe cargar el documento obligatorio: Referencias Bancarias.",
    ]

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_bd = sesion_bd.query(AccesoManual).filter_by(formulario_id=acceso["formulario_id"]).one()
    assert formulario.estado == EstadoFormulario.BORRADOR.value
    assert acceso_bd.consumed_at is None
    assert _documentos_en_bd(sesion_bd, acceso["formulario_id"]) == []
    assert sesion_bd.query(EventoFormulario).filter_by(formulario_id=acceso["formulario_id"]).all() == []
    assert dependencias_dobles["alertas_portal"].eventos == []
    assert dependencias_dobles["extractor_ia"].solicitudes == []


def test_radicacion_rechaza_si_falta_un_documento_requerido_sin_efectos_secundarios(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    documento_omitido = "declaracion_renta"

    subir_documentos_requeridos(
        cliente_api,
        acceso["formulario_id"],
        omitir=documento_omitido,
    )
    _autoguardar_formulario_completo(cliente_api, acceso["formulario_id"])
    respuesta = cliente_api.post(
        f"/api/formularios/{acceso['formulario_id']}/enviar",
        json={
            "credenciales": {
                "token_diligenciamiento": acceso["token_diligenciamiento"],
            },
            "alertas_ignoradas": [
                {
                    "tipo_campo": "razon_social",
                    "nombre_documento": "RUT",
                    "valor_formulario": "Proveedor Integracion SAS",
                    "valor_documento": "Proveedor Integracion",
                    "mensaje": "No debe persistir si la radicacion falla.",
                }
            ],
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "valido": False,
        "errores": [
            {
                "campo": "documentos.declaracion_renta",
                "mensaje": "Debe cargar el documento obligatorio: Declaración de Renta.",
            }
        ],
    }

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_bd = sesion_bd.query(AccesoManual).filter_by(formulario_id=acceso["formulario_id"]).one()
    documentos_activos = {
        documento.tipo_documento: documento
        for documento in sesion_bd.query(DocumentoAdjunto)
        .filter_by(formulario_id=acceso["formulario_id"], deleted_at=None)
        .all()
    }

    assert formulario.estado == EstadoFormulario.BORRADOR.value
    assert acceso_bd.consumed_at is None
    assert documento_omitido not in documentos_activos
    assert TIPO_DOCUMENTO_FORMULARIO_PDF not in documentos_activos
    assert sesion_bd.query(EventoFormulario).filter_by(formulario_id=acceso["formulario_id"]).all() == []
    assert dependencias_dobles["alertas_portal"].eventos == []
    assert len(dependencias_dobles["extractor_ia"].solicitudes) == (
        len(DOCUMENTOS_REQUERIDOS) - 1
    )
    for documento in documentos_activos.values():
        assert documento.ruta_archivo.startswith(f"tmp/{acceso['codigo_peticion']}/")
        assert dependencias_dobles["storage"].existe(documento.ruta_archivo)

    subir_documento(
        cliente_api,
        acceso["formulario_id"],
        tipo_documento=documento_omitido,
        nombre_archivo="declaracion_renta.pdf",
        contenido=contenido_documento(documento_omitido),
    )
    _enviar_formulario(cliente_api, acceso)

    sesion_bd.expire_all()
    formulario = sesion_bd.query(Formulario).filter_by(id=acceso["formulario_id"]).one()
    acceso_bd = sesion_bd.query(AccesoManual).filter_by(formulario_id=acceso["formulario_id"]).one()
    assert formulario.estado == EstadoFormulario.ENVIADO.value
    assert acceso_bd.consumed_at is not None
    assert _documento_activo_en_bd(
        sesion_bd,
        acceso["formulario_id"],
        TIPO_DOCUMENTO_FORMULARIO_PDF,
    )


def test_rechaza_tipo_documental_no_permitido_sin_guardar_evidencia(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)

    respuesta = intentar_subir_documento(
        cliente_api,
        acceso["formulario_id"],
        tipo_documento="documento_desconocido",
        nombre_archivo="documento.pdf",
    )

    assert respuesta.status_code == 422
    assert "Tipo de documento no permitido" in respuesta.json()["detail"]
    assert _documentos_en_bd(sesion_bd, acceso["formulario_id"]) == []
    assert dependencias_dobles["extractor_ia"].solicitudes == []


def test_rechaza_extension_no_permitida_sin_guardar_evidencia(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)

    respuesta = intentar_subir_documento(
        cliente_api,
        acceso["formulario_id"],
        tipo_documento=TIPO_DOCUMENTO_RUT,
        nombre_archivo="rut.txt",
        content_type="application/pdf",
    )

    assert respuesta.status_code == 415
    assert "Extensión no permitida" in respuesta.json()["detail"]
    assert _documentos_en_bd(sesion_bd, acceso["formulario_id"]) == []
    assert dependencias_dobles["extractor_ia"].solicitudes == []


def test_rechaza_content_type_no_permitido_sin_guardar_evidencia(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)

    respuesta = intentar_subir_documento(
        cliente_api,
        acceso["formulario_id"],
        tipo_documento=TIPO_DOCUMENTO_RUT,
        nombre_archivo="rut.pdf",
        content_type="text/plain",
    )

    assert respuesta.status_code == 415
    assert "Tipo de archivo no permitido" in respuesta.json()["detail"]
    assert _documentos_en_bd(sesion_bd, acceso["formulario_id"]) == []
    assert dependencias_dobles["extractor_ia"].solicitudes == []


def test_rechaza_archivo_demasiado_grande_sin_guardar_evidencia(
    cliente_api,
    sesion_bd,
    dependencias_dobles,
):
    acceso = crear_acceso_manual(cliente_api)
    aplicacion_sagrilaft.dependency_overrides[obtener_max_upload_mb] = lambda: 0

    respuesta = intentar_subir_documento(
        cliente_api,
        acceso["formulario_id"],
        tipo_documento=TIPO_DOCUMENTO_RUT,
        nombre_archivo="rut.pdf",
        contenido=b"contenido",
    )

    assert respuesta.status_code == 413
    assert respuesta.json()["detail"] == "El archivo supera el límite permitido de 0 MB."
    assert _documentos_en_bd(sesion_bd, acceso["formulario_id"]) == []
    assert dependencias_dobles["extractor_ia"].solicitudes == []
