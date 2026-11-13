"""Dos circuitos HTTP 2.1, JWT y PostgreSQL desechable; Advanced estrictamente ficticio."""
from datetime import date
from uuid import UUID, uuid4

import pytest
from lxml import etree
from sqlalchemy import func, select, text

from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.persistencia.models import Formulario
from infrastructure.persistencia.modelos_listas import (FuenteLista, VersionFuente, ConsultaLista, ConsultaFuente,
    CoincidenciaLista, EvidenciaConsulta, BorradorConsulta, TrabajoConsulta)
from services.listas.politica_v2 import ActorListas
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from services.listas.importacion_archivos import TrabajadorImportacionArchivos
from .test_flujo_http import portal
from .test_recepcion_f52 import carga, BASE
from .test_administracion_f55 import administracion, identidad, comparar, solicitar, decidir, ejecutar
from .test_busqueda_f62 import activar
from .test_ofac_archivos import FIJO, metadatos
from .soporte_busqueda import habilitar_archivos


def xml_ficticio(anio_nacimiento="1980"):
    raiz = etree.parse(str(FIJO))
    espacio = etree.QName(raiz.getroot()).namespace
    perfiles = raiz.xpath('//*[local-name()="Profile"]')
    perfiles[0].set("PartySubTypeID", "4")
    for ordinal, perfil in enumerate(perfiles):
        for nombre in perfil.xpath('.//*[local-name()="NamePartValue"]'):
            nombre.text = "Persona ficticia Ámbar" if ordinal == 0 else "Empresa ficticia Uno"
    etiqueta = lambda nombre: "{" + espacio + "}" + nombre
    caracteristica = etree.SubElement(perfiles[0], etiqueta("Feature"), ID="999900", FeatureTypeID="8")
    variante = etree.SubElement(caracteristica, etiqueta("FeatureVersion"), ID="999901", ReliabilityID="1560")
    marcas = dict(YearFixed="true", MonthFixed="true", DayFixed="true")
    periodo = etree.SubElement(variante, etiqueta("DatePeriod"), CalendarTypeID="1", **marcas)
    for borde, punto in (("Start", "From"), ("End", "To")):
        limite = etree.SubElement(periodo, etiqueta(borde), Approximate="false", **marcas)
        fecha = etree.SubElement(limite, etiqueta(punto))
        for nombre, valor in (("Year", anio_nacimiento), ("Month", "3"), ("Day", "15")):
            etree.SubElement(fecha, etiqueta(nombre)).text = valor
    etree.SubElement(caracteristica, etiqueta("IdentityReference"), IdentityID="100001", IdentityFeatureLinkTypeID="1")
    return etree.tostring(raiz)


@pytest.fixture
def archivos(administracion, monkeypatch):
    a = administracion
    monkeypatch.setenv("LISTAS_OFAC_LOCAL_HABILITADA", "true")
    fuente_id = uuid4()
    with a.sesiones.begin() as sesion:
        sesion.add(FuenteLista(id=fuente_id, codigo="ofac_sdn", nombre="Advanced ficticio F64", organismo="Ensayo", url_oficial="FIXTURE_LOCAL"))
    contenido = xml_ficticio()
    respuesta = a.cliente.post(BASE, json=metadatos(contenido), headers={"Idempotency-Key":"ofac-f64"})
    assert respuesta.status_code == 201, respuesta.text
    recepcion = respuesta.json()["recepcion_id"]
    assert a.cliente.put(BASE + "/" + recepcion + "/contenido", content=contenido, headers={"Content-Type":"application/octet-stream"}).status_code == 202
    assert TrabajadorValidacionArchivos(a.sesiones, a.custodia, "development", True).ejecutar_uno()
    assert TrabajadorImportacionArchivos(a.sesiones, a.custodia, "development", True).ejecutar_uno()
    with a.sesiones.begin() as sesion:
        version = sesion.scalar(select(VersionFuente).where(VersionFuente.fuente_id == fuente_id))
        assert version.estado == "VALIDA"
        a.fuente, a.version = fuente_id, version.id
        expediente = sesion.get(Formulario, a.expediente)
        expediente.tipo_persona, expediente.razon_social = "juridica", "Empresa ficticia Uno"
        expediente.nombre_representante, expediente.fecha_nacimiento = "Persona ficticia Ámbar", date(1980,3,15)
        expediente.numero_identificacion = expediente.numero_doc_representante = None
    activar(a)
    habilitar_archivos(a,monkeypatch,"ofac_sdn")
    return a


def crear(a, clave="individual", nombre="Persona ficticia Ámbar", nacimiento="1980-03-15", rol="REPRESENTANTE", **extra):
    criterio = dict(tipo_sujeto="PERSONA" if rol == "REPRESENTANTE" else "NO_DETERMINADO", nombre=nombre)
    if nacimiento:
        criterio["fecha_nacimiento"] = nacimiento
    return a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas", headers={"Idempotency-Key":clave},
        json=dict(version_contrato="2.1", sujeto_rol=rol, criterio=criterio, **extra))


def detalle(a, identificador):
    respuesta = a.cliente.get("/api/consultas-listas/" + str(identificador))
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["consulta"]


@pytest.mark.parametrize("nacimiento,nivel,prioritaria", [("1980-03-15","ALTA",False), (None,"MEDIA",False), ("1985-03-15","BAJA",True)])
def test_f64_individual_historial_explicaciones_y_pdf(archivos, nacimiento, nivel, prioritaria):
    a = archivos
    assert a.cliente.get("/api/listas/disponibilidad").json()["consultar"]
    respuesta = crear(a, nacimiento=nacimiento)
    assert respuesta.status_code == 202, respuesta.text
    identificador = respuesta.json()["consulta_id"]
    assert detalle(a, identificador)["estado_ejecucion"] == "PENDIENTE"
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a, identificador)
    assert consulta["version_contrato"] == "2.1" and consulta["estado_ejecucion"] == "COMPLETADA"
    candidato = consulta["candidatos"][0]
    assert candidato["nivel"] == nivel and candidato["revision_prioritaria"] == prioritaria
    assert candidato["explicacion"] and candidato["regla_version"] and candidato["motivos"]
    assert "puntaje" not in candidato
    assert consulta["cobertura"][0]["version_id"] == str(a.version)
    pdf = a.cliente.get(f"/api/consultas-listas/{identificador}/evidencias/{consulta['evidencias'][0]['id']}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with a.sesiones() as sesion:
        guardada = sesion.get(ConsultaLista, UUID(identificador))
        assert guardada.resultado["candidatos"][0] == candidato
        assert guardada.manifiesto["busqueda"]["fuentes"][0]["generacion_id"] == str(a.generacion)
        assert sesion.scalar(select(CoincidenciaLista)).datos_candidato == candidato
        expediente = sesion.get(Formulario, a.expediente)
        assert expediente.estado == "enviado" and expediente.sagrilaft_reporte_id == "reporte-heredado"


def test_f64_grupo_separa_empresa_representante_y_reintento(archivos):
    a = archivos
    ruta = f"/api/expedientes/{a.expediente}/consultas-listas/grupos"
    respuesta = a.cliente.post(ruta, headers={"Idempotency-Key":"grupo"})
    assert respuesta.status_code == 202, respuesta.text
    assert len(respuesta.json()["consultas"]) == 2
    while a.trabajador.ejecutar_uno():
        pass
    consultas = {c["sujeto_rol"]:detalle(a,c["consulta_id"]) for c in respuesta.json()["consultas"]}
    assert consultas["CONTRAPARTE"]["criterio"]["tipo_sujeto"] == "ENTIDAD"
    assert consultas["CONTRAPARTE"]["criterio"]["fecha_nacimiento"] is None
    assert consultas["CONTRAPARTE"]["candidatos"][0]["nivel"] == "MEDIA"
    assert consultas["REPRESENTANTE"]["candidatos"][0]["nivel"] == "ALTA"
    with a.sesiones.begin() as sesion:
        sesion.get(Formulario, a.expediente).nombre_representante = "Cambio posterior"
    assert a.cliente.post(ruta,headers={"Idempotency-Key":"grupo"}).json() == respuesta.json()


def test_f64_natural_un_sujeto_y_no_se_agrega_nacimiento_a_nombre_editado(archivos):
    a = archivos
    with a.sesiones.begin() as sesion:
        sesion.get(Formulario,a.expediente).tipo_persona = "natural"
    ruta = f"/api/expedientes/{a.expediente}/consultas-listas/grupos"
    grupo = a.cliente.post(ruta,headers={"Idempotency-Key":"natural"})
    assert grupo.status_code == 202, grupo.text
    assert len(grupo.json()["consultas"]) == 1
    assert grupo.json()["no_consultados"][0]["motivo"] == "BLOQUE_PERSONAL_ES_CONTRAPARTE"
    assert crear(a).status_code == 422
    respuesta = crear(a, clave="nombre-editado", nombre="Persona ficticia", nacimiento=None, rol="CONTRAPARTE")
    assert respuesta.status_code == 202, respuesta.text
    while a.trabajador.ejecutar_uno():
        pass
    consulta = detalle(a,respuesta.json()["consulta_id"])
    assert consulta["criterio"]["fecha_nacimiento"] is None
    assert consulta["candidatos"][0]["nivel"] == "BAJA"


@pytest.mark.parametrize("roles,estado", [([],403),(["acceso_proveedores","listas_revisor"],404),(["acceso_clientes"],403)])
def test_f64_permisos_reales_en_ambos_circuitos(archivos,roles,estado):
    a = archivos
    a.cliente.headers["Authorization"] = "Bearer " + a.token(roles)
    assert crear(a).status_code == estado
    assert a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas/grupos",headers={"Idempotency-Key":"sin-permiso"}).status_code == estado


def test_f64_reintento_conserva_criterio_y_cambio_config_no_altera_historia(archivos,monkeypatch):
    a = archivos
    primera = crear(a)
    assert primera.status_code == 202, primera.text
    with a.sesiones.begin() as sesion:
        sesion.get(Formulario,a.expediente).tipo_persona = "natural"
    a.app.state.config.listas_cautela = SagrilaftListasConfig(proveedor="deshabilitado")
    monkeypatch.delenv("LISTAS_ARCHIVOS_POLITICA_ID")
    assert crear(a).json() == primera.json()
    assert crear(a,nombre="Otro nombre").status_code == 409
    assert a.trabajador.ejecutar_uno()
    assert detalle(a,primera.json()["consulta_id"])["candidatos"][0]["nivel"] == "ALTA"


def test_f64_fuente_requerida_ausente_queda_fallida_no_concluyente(archivos,monkeypatch):
    a = archivos
    monkeypatch.setenv("LISTAS_ARCHIVOS_FUENTES","ofac_sdn,fuente_inexistente")
    respuesta = crear(a)
    assert respuesta.status_code == 202, respuesta.text
    consulta = detalle(a,respuesta.json()["consulta_id"])
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert not consulta["candidatos"] and not a.trabajador.ejecutar_uno()


def test_f64_no_acepta_manifesto_actor_o_version_impropios(archivos):
    a = archivos
    assert crear(a,manifiesto={}).status_code == 422
    assert crear(a,actor={}).status_code == 422
    antigua = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",headers={"Idempotency-Key":"v20"},
        json={"criterio":{"tipo_sujeto":"PERSONA","nombre":"Persona ficticia"}})
    assert antigua.status_code == 409


def bloquear(a):
    from infrastructure.persistencia.repositorios.administracion_listas import RepositorioAdministracionListas
    actor = ActorListas.desde_identidad_validada(a.app.state.config.keycloak.issuer, "incidentes", ("listas_incidentes",))
    RepositorioAdministracionListas(a.sesiones, a.busqueda.politica, a.custodia, lambda *_: None).bloquear(actor, a.version, "Ensayo F64")


def test_f64_bloqueo_posterior_no_sustituye_version(archivos):
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    bloquear(a)
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a, identificador)
    assert consulta["estado_ejecucion"] == "FALLIDA"
    assert consulta["conclusion_busqueda"] == "NO_CONCLUYENTE" and not consulta["candidatos"]
    assert consulta["cobertura"][0]["version_id"] == str(a.version)


def test_f64_recupera_borrador_sin_repetir_motor(archivos, monkeypatch):
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    original = a.trabajador.repositorio.preparar_informe
    def interrumpir(*_):
        raise RuntimeError("Interrupción después del borrador")
    monkeypatch.setattr(a.trabajador.repositorio, "preparar_informe", interrumpir)
    with pytest.raises(RuntimeError, match="Interrupción"):
        a.trabajador.ejecutar_uno()
    with a.sesiones.begin() as sesion:
        borrador = sesion.scalar(select(BorradorConsulta))
        resultado = borrador.resultado
        sesion.execute(text("UPDATE trabajo_consulta SET concesion_hasta=now()-interval '1 second' WHERE consulta_id=:id"), {"id":identificador})
    monkeypatch.setattr(a.trabajador.repositorio, "preparar_informe", original)
    monkeypatch.setattr("infrastructure.listas.consultor_archivos.ConsultorArchivos.consultar", lambda *_: pytest.fail("No debe repetirse el motor"))
    assert a.trabajador.ejecutar_uno()
    assert not a.trabajador.ejecutar_uno()
    assert detalle(a, identificador)["candidatos"] == resultado["candidatos"]
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(CoincidenciaLista)) == 1
        assert sesion.scalar(select(func.count()).select_from(EvidenciaConsulta)) == 1


def test_f64_limite_evaluacion_no_cierra_como_completa(archivos, monkeypatch):
    from services.listas import admision_archivos
    original = admision_archivos.ParametrosMotor
    monkeypatch.setattr(admision_archivos, "ParametrosMotor", lambda **datos: original(**({"maximo_registros":1} | datos)))
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    monkeypatch.setattr(admision_archivos, "ParametrosMotor", original)
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a,identificador)
    assert consulta["estado_ejecucion"] == "PARCIAL" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"


def test_f64_dos_solicitudes_simultaneas_solo_admiten_una(archivos):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    a = archivos
    barrera = Barrier(2)
    def solicitar_una(_):
        barrera.wait()
        respuesta = crear(a)
        assert respuesta.status_code == 202, respuesta.text
        return respuesta.json()
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        respuestas = list(ejecutor.map(solicitar_una, range(2)))
    assert respuestas[0] == respuestas[1]
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 1
        assert sesion.scalar(select(func.count()).select_from(TrabajoConsulta)) == 1


def test_f64_fallo_segundo_sujeto_revierte_grupo_completo(archivos, monkeypatch):
    from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
    from infrastructure.persistencia.modelos_grupos_listas import GrupoConsultaLista
    a = archivos
    original = RepositorioConsultasListas.admitir
    llamadas = []
    def admitir(*argumentos, **opciones):
        llamadas.append(True)
        if len(llamadas) == 2:
            raise RuntimeError("Fallo de persistencia del segundo sujeto")
        return original(*argumentos, **opciones)
    monkeypatch.setattr(RepositorioConsultasListas, "admitir", admitir)
    with pytest.raises(RuntimeError, match="segundo sujeto"):
        a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas/grupos", headers={"Idempotency-Key":"fallido"})
    with a.sesiones() as sesion:
        for tabla in (ConsultaLista, ConsultaFuente, TrabajoConsulta, GrupoConsultaLista):
            assert sesion.scalar(select(func.count()).select_from(tabla)) == 0


def test_f64_navegador_con_ambos_circuitos_y_revision_humana(archivos, tmp_path):
    from .test_flujo_http import test_navegador_con_api_postgres_y_trabajador_reales as recorrido
    recorrido(archivos, tmp_path, "ninguno")
    import os
    import shutil
    from pathlib import Path
    evidencias = Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"])
    shutil.copyfile(evidencias / "portal-ninguno.png", evidencias / "portal-archivos.png")
    with archivos.sesiones() as sesion:
        consultas = list(sesion.scalars(select(ConsultaLista)))
        assert len(consultas) == 3
        assert all(c.version_contrato == "2.1" and c.estado == "COMPLETADA" for c in consultas)


def test_f64_activacion_y_reversion_no_reescriben_consulta_admitida(archivos):
    a = archivos
    anterior = crear(a).json()["consulta_id"]
    version_anterior = a.version
    identidad(a)
    contenido = xml_ficticio("1982")
    respuesta = a.cliente.post(BASE, json=metadatos(contenido), headers={"Idempotency-Key":"ofac-f64-nueva"})
    assert respuesta.status_code == 201, respuesta.text
    recepcion = respuesta.json()["recepcion_id"]
    assert a.cliente.put(BASE + "/" + recepcion + "/contenido", content=contenido, headers={"Content-Type":"application/octet-stream"}).status_code == 202
    assert TrabajadorValidacionArchivos(a.sesiones,a.custodia,"development",True).ejecutar_uno()
    assert TrabajadorImportacionArchivos(a.sesiones,a.custodia,"development",True).ejecutar_uno(), a.cliente.get(BASE + "/" + recepcion + "/validacion").text
    with a.sesiones() as sesion:
        nueva = sesion.scalar(select(VersionFuente).where(VersionFuente.fuente_id == a.fuente, VersionFuente.id != version_anterior))
        nueva_id = nueva.id
    actor = ActorListas.desde_identidad_validada(a.app.state.config.keycloak.issuer,"operador-local",("listas_cargador",))
    a.busqueda.preparar(actor,nueva_id)
    comparacion = comparar(a,nueva_id,1,"comparacion-v2")
    solicitud = solicitar(a,comparacion,clave="solicitud-v2")
    identidad(a,"revisor",("listas_aprobador",))
    aprobacion = decidir(a,solicitud,clave="aprobacion-v2").json()["revision_id"]
    respuesta = ejecutar(a,solicitud,aprobacion,1,"ejecucion-v2")
    assert respuesta.status_code == 200, respuesta.text
    a.cliente.headers["Authorization"] = "Bearer " + a.token()
    posterior = crear(a,clave="consulta-v2").json()["consulta_id"]
    while a.trabajador.ejecutar_uno():
        pass
    primera, segunda = detalle(a,anterior), detalle(a,posterior)
    assert primera["cobertura"][0]["version_id"] == str(version_anterior)
    assert primera["candidatos"][0]["nivel"] == "ALTA"
    assert segunda["cobertura"][0]["version_id"] == str(nueva_id)
    assert segunda["candidatos"][0]["nivel"] == "BAJA"
    ruta_pdf = f"/api/consultas-listas/{posterior}/evidencias/{segunda['evidencias'][0]['id']}"
    pdf = a.cliente.get(ruta_pdf).content
    identidad(a)
    comparacion = comparar(a,version_anterior,2,"comparacion-reversion")
    solicitud = solicitar(a,comparacion,tipo="REVERSION",clave="reversion")
    identidad(a,"revisor",("listas_aprobador",))
    aprobacion = decidir(a,solicitud,clave="aprobar-reversion").json()["revision_id"]
    respuesta = ejecutar(a,solicitud,aprobacion,2,"ejecutar-reversion")
    assert respuesta.status_code == 200, respuesta.text
    a.cliente.headers["Authorization"] = "Bearer " + a.token()
    assert detalle(a,posterior) == segunda
    assert a.cliente.get(ruta_pdf).content == pdf


def test_f64_bloqueo_entre_borrador_y_cierre_no_confirma_resultado(archivos,monkeypatch):
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    original = a.trabajador.repositorio.preparar_informe
    def informar_y_bloquear(concesion):
        resultado = original(concesion)
        bloquear(a)
        return resultado
    monkeypatch.setattr(a.trabajador.repositorio,"preparar_informe",informar_y_bloquear)
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a,identificador)
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert not consulta["candidatos"] and not consulta["evidencias"]


# --- Botón 1 ("consultar contraparte"): el país del documento ahora se acepta y se valida,
# en vez de quedar siempre ausente. Un código inventado se rechaza; uno real se admite.
def test_f64_boton_individual_rechaza_pais_emisor_inventado(archivos):
    a = archivos
    respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",
        headers={"Idempotency-Key": "pais-invalido"},
        json=dict(version_contrato="2.1", sujeto_rol="REPRESENTANTE",
            criterio=dict(tipo_sujeto="PERSONA", nombre="Persona ficticia Ámbar",
                identificadores=[dict(tipo="NIT", valor="900123456", pais_emisor="ZZ")])))
    assert respuesta.status_code == 422, respuesta.text


def test_f64_boton_individual_acepta_pais_emisor_declarado(archivos):
    a = archivos
    respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",
        headers={"Idempotency-Key": "pais-valido"},
        json=dict(version_contrato="2.1", sujeto_rol="REPRESENTANTE",
            criterio=dict(tipo_sujeto="PERSONA", nombre="Persona ficticia Ámbar",
                identificadores=[dict(tipo="NIT", valor="900123456", pais_emisor="CO")])))
    assert respuesta.status_code == 202, respuesta.text
    identificador = respuesta.json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a, identificador)
    assert consulta["estado_ejecucion"] == "COMPLETADA"
    assert consulta["criterio"]["identificadores"][0]["pais_emisor"] == "CO"


# --- Botón 1 ("consultar contraparte"): la fecha de nacimiento ahora se acepta igual que el
# país, precargada y editable en el portal; el servidor no la agrega por su cuenta, solo la
# usa si el criterio la trae declarada explícitamente.
def test_f64_boton_individual_acepta_fecha_nacimiento_declarada(archivos):
    a = archivos
    respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",
        headers={"Idempotency-Key": "nacimiento-declarado"},
        json=dict(version_contrato="2.1", sujeto_rol="REPRESENTANTE",
            criterio=dict(tipo_sujeto="PERSONA", nombre="Persona ficticia Ámbar",
                fecha_nacimiento="1980-03-15")))
    assert respuesta.status_code == 202, respuesta.text
    identificador = respuesta.json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a, identificador)
    assert consulta["estado_ejecucion"] == "COMPLETADA"
    assert consulta["criterio"]["fecha_nacimiento"] == "1980-03-15"
    assert consulta["candidatos"][0]["nivel"] == "ALTA"


def test_f64_boton_individual_sin_fecha_nunca_confirma_por_nacimiento(archivos):
    """Sin fecha declarada, no puede existir la vía 'nombre + nacimiento exacto'; el
    nivel queda sostenido únicamente por lo que sí se comparó (el nombre)."""
    a = archivos
    respuesta = a.cliente.post(f"/api/expedientes/{a.expediente}/consultas-listas",
        headers={"Idempotency-Key": "sin-nacimiento"},
        json=dict(version_contrato="2.1", sujeto_rol="REPRESENTANTE",
            criterio=dict(tipo_sujeto="PERSONA", nombre="Persona ficticia Ámbar")))
    assert respuesta.status_code == 202, respuesta.text
    identificador = respuesta.json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a, identificador)
    assert "fecha_nacimiento" not in consulta["criterio"] or consulta["criterio"]["fecha_nacimiento"] is None
    assert consulta["candidatos"][0]["nivel"] == "MEDIA"
