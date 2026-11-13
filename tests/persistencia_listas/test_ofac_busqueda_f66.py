"""Cuatro anclas oficiales sobre el ZIP conocido. Solo arnés desechable y optativo."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func, text

from domain.listas.administracion import RecepcionPropuesta
from infrastructure.listas.recepcion_archivo import ArchivoEnRecepcion
from infrastructure.persistencia.modelos_listas import FuenteLista, VersionFuente, PoliticaListas, RegistroLista, ConsultaLista
from services.listas.informes import calcular_huella
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from services.listas.importacion_archivos import TrabajadorImportacionArchivos
from .test_flujo_http import portal
from .test_recepcion_f52 import carga
from .test_busqueda_f62 import activar
from .test_administracion_f55 import identidad
from .soporte_busqueda import habilitar_archivos


@pytest.mark.skipif(not os.environ.get("LISTAS_OFAC_ENSAYO_ARCHIVO"),reason="Requiere --archivo-ofac con el ZIP local conocido")
def test_f66_ofac_oficial_recorrido_completo(carga,monkeypatch):
    from api.routers import administracion_versiones
    a = carga
    a.app.include_router(administracion_versiones.enrutador)
    origen = Path(os.environ["LISTAS_OFAC_ENSAYO_ARCHIVO"])
    resultados = Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"])
    evidencia = dict(alcance="OFAC_LOCAL_DESECHABLE_R01_R04",estado="EN_CURSO",etapas={},consultas=[])
    inicio = time.perf_counter()
    def guardar(etapa):
        evidencia.update(etapa=etapa,segundos_totales=round(time.perf_counter()-inicio,3))
        (resultados/"ofac-f66.json").write_text(json.dumps(evidencia,ensure_ascii=False,indent=2)+"\n")
    guardar("PREPARACION")
    try:
        resumen = hashlib.sha256()
        with origen.open("rb") as entrada:
            while bloque := entrada.read(65536): resumen.update(bloque)
        assert origen.suffix.lower() == ".zip" and resumen.hexdigest() == "5b3a008cf8311f88f26c0b6da888a1271919fd30d5dc712f24073eb77791726c"
        evidencia["archivo"] = dict(nombre=origen.name,sha256=resumen.hexdigest(),bytes=origen.stat().st_size,
            fecha_descarga_original="NO_INFORMADA",fecha_recepcion_ensayo=datetime.now(timezone.utc).isoformat())
        monkeypatch.setenv("LISTAS_OFAC_LOCAL_HABILITADA","true")
        with a.sesiones.begin() as sesion:
            sesion.add(FuenteLista(codigo="ofac_sdn",nombre="OFAC SDN ensayo F66",organismo="OFAC",url_oficial="https://sanctionslist.ofac.treas.gov/Home/SdnList"))
        etapa = time.perf_counter()
        propuesta = RecepcionPropuesta(fuente="ofac_sdn",formato="OFAC_ADVANCED_ZIP_V3",nombre_original=origen.name,
            procedencia="https://sanctionslist.ofac.treas.gov/Home/SdnList",descargado_en=evidencia["archivo"]["fecha_recepcion_ensayo"],
            huella_declarada=resumen.hexdigest(),clave="ofac-f66-local")
        recepcion = a.servicio.reservar(propuesta)
        concesion = a.servicio.reclamar(recepcion)
        escritura = ArchivoEnRecepcion(a.custodia,a.servicio.perfil.recibido_bytes)
        try:
            with origen.open("rb") as entrada:
                while bloque := entrada.read(65536): escritura.escribir(bloque)
            a.servicio.confirmar(recepcion,concesion[0],escritura.confirmar(resumen.hexdigest()))
        finally: escritura.cerrar()
        evidencia["etapas"]["recepcion_segundos"] = round(time.perf_counter()-etapa,3)
        guardar("VALIDACION")
        etapa = time.perf_counter()
        assert TrabajadorValidacionArchivos(a.sesiones,a.custodia,"development",True).ejecutar_uno()
        evidencia["etapas"]["validacion_segundos"] = round(time.perf_counter()-etapa,3)
        guardar("IMPORTACION")
        etapa = time.perf_counter()
        def avance(paso, trabajo):
            if paso == "despues_commit_lote":
                evidencia["etapas"]["importacion_transcurrida_segundos"] = round(time.perf_counter()-etapa,3)
                guardar("IMPORTACION")
        assert TrabajadorImportacionArchivos(a.sesiones,a.custodia,"development",True,observador=avance).ejecutar_uno()
        evidencia["etapas"]["importacion_segundos"] = round(time.perf_counter()-etapa,3)
        with a.sesiones.begin() as sesion:
            version = sesion.scalar(select(VersionFuente))
            assert version.estado == "VALIDA" and version.cantidad_registros == 19563
            assert sesion.scalar(select(func.count(func.distinct(RegistroLista.uid_original)))) == 19563
            a.version,a.fuente,a.politica_id = version.id,version.fuente_id,uuid4()
            parametros = {"solo_pruebas":True}
            sesion.add(PoliticaListas(id=a.politica_id,codigo="f66-oficial-local",version=1,parametros=parametros,
                huella=calcular_huella(parametros),aprobador_emisor=a.app.state.config.keycloak.issuer,aprobador_sujeto="revisor-local"))
            evidencia["publicacion_xml"] = version.publicada_en
        monkeypatch.setenv("LISTAS_ADMIN_POLITICA_ID",str(a.politica_id))
        guardar("ACTIVACION_LOCAL_DOS_PERSONAS")
        etapa = time.perf_counter()
        identidad(a)
        activar(a)
        evidencia["etapas"]["activacion_segundos"] = round(time.perf_counter()-etapa,3)
        guardar("GENERACION_BUSQUEDA")
        etapa = time.perf_counter()
        habilitar_archivos(a,monkeypatch,"ofac_sdn")
        evidencia["etapas"]["generacion_segundos"] = round(time.perf_counter()-etapa,3)
        casos = [("R-01","Nicolás Maduro Moros","PERSONA",None,"22790"),
                 ("R-02","Nicolás Maduro Moros","PERSONA","1962-11-23","22790"),
                 ("R-03","OJSC Rosneft Oil Company","ENTIDAD",None,"17022"),
                 ("R-04","Rosneft","ENTIDAD",None,"17022")]
        from infrastructure.persistencia.models import Formulario
        for caso,nombre,tipo,nacimiento,uid in casos:
            guardar(caso)
            a.cliente.headers["Authorization"] = "Bearer " + a.token()
            with a.sesiones.begin() as sesion:
                sesion.get(Formulario,a.expediente).tipo_persona = "natural" if tipo == "PERSONA" else "juridica"
            etapa = time.perf_counter()
            criterio = dict(tipo_sujeto=tipo,nombre=nombre,**({"fecha_nacimiento":nacimiento} if nacimiento else {}))
            respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",headers={"Idempotency-Key":caso},
                json=dict(version_contrato="2.1",criterio=criterio))
            assert respuesta.status_code == 202,respuesta.text
            admision = time.perf_counter()-etapa
            identificador = respuesta.json()["consulta_id"]
            etapa = time.perf_counter()
            assert a.trabajador.ejecutar_uno()
            ejecucion = time.perf_counter()-etapa
            respuesta = a.cliente.get("/api/consultas-listas/"+identificador)
            assert respuesta.status_code == 200,respuesta.text
            consulta = respuesta.json()["consulta"]
            with a.sesiones() as sesion:
                objetivo = sesion.scalar(select(RegistroLista.id).where(RegistroLista.version_id == a.version,RegistroLista.uid_original == uid))
                candidato = next(c for c in consulta["candidatos"] if c["registro_id"] == str(objetivo))
                assert candidato["nivel"] == "MEDIA" and consulta["estado_ejecucion"] == "COMPLETADA",consulta
                assert sesion.get(ConsultaLista,UUID(identificador)).manifiesto["busqueda"]["fuentes"][0]["generacion_id"] == str(a.generacion)
            evidencia_pdf = consulta["evidencias"][0]
            etapa = time.perf_counter()
            pdf = a.cliente.get(f"/api/consultas-listas/{identificador}/evidencias/{evidencia_pdf['id']}")
            assert pdf.status_code == 200 and hashlib.sha256(pdf.content).hexdigest() == evidencia_pdf["sha256"]
            evidencia["consultas"].append(dict(caso=caso,uid_objetivo=uid,nivel=candidato["nivel"],
                candidatos=len(consulta["candidatos"]),estado=consulta["estado_ejecucion"],
                admision_segundos=round(admision,3),trabajador_y_pdf_segundos=round(ejecucion,3),
                descarga_pdf_segundos=round(time.perf_counter()-etapa,3),pdf_bytes=len(pdf.content)))
        with a.sesiones() as sesion:
            evidencia["base_datos_bytes"] = sesion.scalar(text("SELECT pg_database_size(current_database())"))
        evidencia["memoria_maxima_proceso_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        evidencia["custodia_bytes"] = sum(p.stat().st_size for p in a.custodia.directorio.iterdir() if p.is_file())
        evidencia["estado"] = "APROBADO"
        guardar("FINALIZADO")
    except BaseException as error:
        evidencia.update(estado="FALLIDO",error=dict(tipo=type(error).__name__,mensaje=str(error)[:2000]))
        guardar("FALLO")
        raise
