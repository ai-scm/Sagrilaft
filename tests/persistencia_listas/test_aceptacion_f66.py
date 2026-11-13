"""26 identificadores de aceptación: reglas por HTTP y controles operativos reales."""
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import UUID

import pytest
from sqlalchemy import select,func

from infrastructure.persistencia.models import Formulario, ResultadoValidacion
from infrastructure.persistencia.modelos_listas import ConsultaLista, VersionFuente, RevisionCumplimiento
from infrastructure.listas.adaptadores_busqueda import LECTORES
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from services.listas.importacion_archivos import TrabajadorImportacionArchivos
from tests.contracts.test_motor_busqueda_f63 import CASOS_PRIORITARIOS_MOTOR, caso_prioritario, empresa, persona, consulta, NOMBRE
from . import adaptador_aceptacion_f66
from .soporte_busqueda import habilitar_archivos
from .test_flujo_http import portal
from .test_recepcion_f52 import carga, reservar, enviar
from .test_administracion_f55 import administracion, identidad
from .test_busqueda_f62 import activar
from .test_integracion_f64 import (archivos,crear,detalle,
    test_f64_fuente_requerida_ausente_queda_fallida_no_concluyente as comprobar_fuente_ausente,
    test_f64_activacion_y_reversion_no_reescriben_consulta_admitida as comprobar_cambio_reversion)


def registrar(datos):
    with (Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"])/"aceptacion-f66.jsonl").open("a") as salida:
        salida.write(json.dumps(datos,ensure_ascii=False)+"\n")


@pytest.mark.parametrize("caso",CASOS_PRIORITARIOS_MOTOR+["B-08"])
def test_f66_clasificacion_por_http_con_historial_y_pdf(administracion,monkeypatch,caso):
    a = administracion
    if caso == "B-08":
        criterio,registros,esperados = consulta("Comercial Andina S.A.S.",naturaleza="ENTIDAD"),[empresa(),persona()],["MEDIA"]
    else:
        criterio,registros,esperados = caso_prioritario(caso)
    contenido = adaptador_aceptacion_f66.xml_de_registros(registros)
    identidad(a)
    recepcion = reservar(a,"caso-"+caso,contenido)
    assert enviar(a,recepcion,contenido).status_code == 202
    assert TrabajadorValidacionArchivos(a.sesiones,a.custodia,"development",True).ejecutar_uno()
    assert TrabajadorImportacionArchivos(a.sesiones,a.custodia,"development",True).ejecutar_uno()
    with a.sesiones() as sesion:
        a.version = sesion.scalar(select(VersionFuente.id).where(VersionFuente.id != a.version))
    activar(a)
    monkeypatch.setitem(LECTORES,"SINTETICO_XML_V1",adaptador_aceptacion_f66)
    habilitar_archivos(a,monkeypatch,"ofac_sdn_prueba")
    for comercial in ("cliente","proveedor"):
        roles = ("CONTRAPARTE","REPRESENTANTE") if criterio.tipo_sujeto == "PERSONA" else ("CONTRAPARTE",)
        for sujeto in roles:
            with a.sesiones.begin() as sesion:
                expediente = sesion.get(Formulario,a.expediente)
                expediente.tipo_contraparte = comercial
                expediente.tipo_persona = "natural" if criterio.tipo_sujeto == "PERSONA" and sujeto == "CONTRAPARTE" else "juridica"
            a.cliente.headers["Authorization"] = "Bearer "+a.token(["acceso_clientes","acceso_proveedores","listas_revisor"])
            inicio = time.perf_counter()
            respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",headers={"Idempotency-Key":f"{caso}-{comercial}-{sujeto}"},
                json=dict(version_contrato="2.1",sujeto_rol=sujeto,criterio=criterio.model_dump(mode="json")))
            assert respuesta.status_code == 202,respuesta.text
            admision = time.perf_counter()-inicio
            identificador = respuesta.json()["consulta_id"]
            comienzo_motor = time.perf_counter()
            assert a.trabajador.ejecutar_uno()
            ejecucion = time.perf_counter()-comienzo_motor
            resultado = detalle(a,identificador)
            assert resultado["estado_ejecucion"] == "COMPLETADA",resultado
            assert sorted(c["nivel"] for c in resultado["candidatos"]) == sorted(esperados),resultado
            for candidato in resultado["candidatos"]:
                assert candidato["revision_prioritaria"] == (caso in {"C-02","C-03","B-06","B-07"})
                assert candidato["motivos"] and candidato["explicacion"]
            assert resultado["conclusion_busqueda"] == ("CON_CANDIDATOS" if esperados else "SIN_CANDIDATOS")
            evidencia = resultado["evidencias"][0]
            pdf = a.cliente.get(f"/api/consultas-listas/{identificador}/evidencias/{evidencia['id']}")
            assert pdf.status_code == 200 and hashlib.sha256(pdf.content).hexdigest() == evidencia["sha256"]
            assert resultado["trazabilidad"]["fuentes"][0]["version_id"] == str(a.version)
            with a.sesiones() as sesion:
                guardada = sesion.get(ConsultaLista,UUID(identificador))
                assert guardada.resultado["candidatos"] == resultado["candidatos"]
                assert sesion.get(Formulario,a.expediente).estado == "enviado"
            registrar(dict(caso=caso,rol=comercial,sujeto=sujeto,esperados=esperados,
                candidatos=resultado["candidatos"],estado=resultado["estado_ejecucion"],
                admision_segundos=admision,trabajador_y_pdf_segundos=ejecucion,recorrido_segundos=time.perf_counter()-inicio,pdf_bytes=len(pdf.content)))
        if caso == "B-08":
            with a.sesiones.begin() as sesion:
                expediente = sesion.get(Formulario,a.expediente)
                expediente.razon_social,expediente.nombre_representante = "Comercial Andina S.A.S.",NOMBRE
                expediente.numero_identificacion = expediente.numero_doc_representante = None
                expediente.fecha_nacimiento = date(1980,3,15)
            grupo = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas/grupos",headers={"Idempotency-Key":"B08-grupo-"+comercial})
            assert grupo.status_code == 202,grupo.text
            while a.trabajador.ejecutar_uno(): pass
            niveles = {c["sujeto_rol"]:detalle(a,c["consulta_id"])["candidatos"][0]["nivel"] for c in grupo.json()["consultas"]}
            assert niveles == {"CONTRAPARTE":"MEDIA","REPRESENTANTE":"ALTA"}
            registrar(dict(caso=caso,rol=comercial,circuito="GRUPO",niveles=niveles))


def test_f66_O02_fuente_requerida_ausente(archivos,monkeypatch):
    comprobar_fuente_ausente(archivos,monkeypatch)
    registrar(dict(caso="O-02",resultado="NO_CONCLUYENTE sin fuente requerida"))


def test_f66_O03_O04_cambio_y_restauracion_conservan_historia(archivos):
    comprobar_cambio_reversion(archivos)
    for caso in ("O-03","O-04"):
        registrar(dict(caso=caso,resultado="Versión, candidatos y PDF conservados"))


def test_f66_O11_permisos_consulta_historial_y_pdf(archivos):
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    evidencia = detalle(a,identificador)["evidencias"][0]["id"]
    for roles,estado in (([],403),(["acceso_clientes"],403),(["acceso_proveedores","listas_revisor"],404)):
        a.cliente.headers["Authorization"] = "Bearer "+a.token(roles)
        assert crear(a,clave="sin-acceso").status_code == estado
        assert a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas/grupos",headers={"Idempotency-Key":"sin-acceso"}).status_code == estado
        for ruta in (f"/api/expedientes/{a.expediente}/consultas-listas",f"/api/consultas-listas/{identificador}",f"/api/consultas-listas/{identificador}/evidencias/{evidencia}"):
            assert a.cliente.get(ruta).status_code == estado
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 1
    registrar(dict(caso="O-11",resultado="Consultas, historial y PDF denegados sin acceso"))


def test_f66_O12_alta_y_revision_no_modifican_negocio(archivos):
    a = archivos
    def negocio():
        with a.sesiones() as sesion:
            return dict(sesion.execute(select(Formulario.__table__).where(Formulario.id == a.expediente)).mappings().one()),sesion.scalar(select(func.count()).select_from(ResultadoValidacion))
    anterior = negocio()
    identificador = crear(a).json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    resultado = detalle(a,identificador)
    assert resultado["candidatos"][0]["nivel"] == "ALTA" and negocio() == anterior
    ruta = f"/api/consultas-listas/{identificador}/evidencias/{resultado['evidencias'][0]['id']}"
    pdf = a.cliente.get(ruta).content
    revision = a.cliente.post(f"/api/consultas-listas/{identificador}/revisiones",json=dict(resultado="IDENTIDAD_CORROBORADA",justificacion="Identidad revisada por una persona; no decide riesgo ni estado comercial"))
    assert revision.status_code == 201,revision.text
    assert negocio() == anterior and a.cliente.get(ruta).content == pdf
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(RevisionCumplimiento)) == 1
    registrar(dict(caso="O-12",resultado="ALTA y revisión humana sin cambios comerciales ni PDF reescrito"))
