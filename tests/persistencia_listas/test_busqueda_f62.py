"""F6.2 con PostgreSQL desechable y fuentes sintéticas; sin motor de búsqueda."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from domain.listas.catalogos_busqueda import CatalogoPreparacion, IDENTIFICADORES_INICIALES
from domain.listas.errores import ErrorIntegridadEvidencia, VersionNoDisponible
from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda, RegistroBusquedaPersistido, TerminoBusqueda
from infrastructure.persistencia.modelos_listas import FuenteVersionActiva, RegistroLista, VersionFuente
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from .test_flujo_http import portal
from .test_recepcion_f52 import carga
from .test_administracion_f55 import administracion, aprobada, ejecutar, identidad, solicitar, decidir, comparar


@pytest.fixture
def busqueda(administracion):
    a = administracion
    a.actor = ActorListas.desde_identidad_validada(a.app.state.config.keycloak.issuer, "operador-local", ("listas_cargador",))
    a.busqueda = RepositorioBusquedaListas(a.sesiones, a.custodia,
        PoliticaListasV2(a.app.state.config.listas_cautela, "development"),
        CatalogoPreparacion(version="ensayo-v1", identificadores=IDENTIFICADORES_INICIALES))
    return a


def activar(a):
    solicitud, aprobacion = aprobada(a)
    respuesta = ejecutar(a, solicitud, aprobacion)
    assert respuesta.status_code == 200, respuesta.text


def fijar(a, generacion):
    with a.sesiones.begin() as sesion:
        return a.busqueda.fijar_activas(sesion, {"ofac_sdn_prueba": generacion})[0]


def test_f62_prepara_sin_alterar_originales_y_lee_sin_xml(busqueda, monkeypatch):
    a = busqueda
    with a.sesiones() as sesion:
        anteriores = [(r.id, r.huella_semantica, r.contenido_original) for r in sesion.scalars(select(RegistroLista).order_by(RegistroLista.id))]
    generacion = a.busqueda.preparar(a.actor, a.version)
    assert a.busqueda.preparar(a.actor, a.version) == generacion
    with pytest.raises(VersionNoDisponible):
        fijar(a, generacion)
    activar(a)
    fijada = fijar(a, generacion)
    monkeypatch.setattr("infrastructure.persistencia.repositorios.busqueda_listas.verificar_version",
                        lambda *_: pytest.fail("La lectura no debe abrir originales"))
    with a.sesiones.begin() as sesion:
        lectura = a.busqueda.leer_fijada(sesion, fijada)
        registros = lectura.registros
        assert lectura.no_interpretados  # El tipo PRUEBA no se presenta como criterio aplicado.
        assert not lectura.excluidos
        assert len(registros) == 2
        assert sum(len(r.nombres) for r in registros) == 3
        persona = next(r for r in registros if r.tipo_sujeto == "PERSONA")
        assert persona.identificadores[0].valor == "00001"
        assert persona.relaciones[0].version_destino_id == a.version
        assert sesion.scalar(select(func.count()).select_from(TerminoBusqueda)) == 4
        assert anteriores == [(r.id, r.huella_semantica, r.contenido_original) for r in sesion.scalars(select(RegistroLista).order_by(RegistroLista.id))]


def test_f62_rechaza_sin_permiso_identidad_o_version(busqueda):
    a = busqueda
    for actor in [ActorListas("", "operador-local", frozenset({"listas.comparar"})),
                  ActorListas("emisor", "sin-permiso", frozenset())]:
        with pytest.raises(PermissionError):
            a.busqueda.preparar(actor, a.version)
    with pytest.raises(VersionNoDisponible):
        a.busqueda.preparar(a.actor, uuid4())


@pytest.mark.parametrize("etapa", ["registro_preparado", "antes_confirmar"])
def test_f62_fallo_revierte_generacion_completa_y_reintenta(busqueda, etapa):
    a = busqueda
    def fallar(paso, _):
        if paso == etapa:
            raise OSError("Fallo local inyectado")
    with pytest.raises(OSError):
        a.busqueda.preparar(a.actor, a.version, fallar)
    with a.sesiones() as sesion:
        for tabla in (GeneracionBusqueda, RegistroBusquedaPersistido, TerminoBusqueda):
            assert sesion.scalar(select(func.count()).select_from(tabla)) == 0
    assert a.busqueda.preparar(a.actor, a.version)


def test_f62_concurrencia_devuelve_una_generacion(busqueda):
    a = busqueda
    with ThreadPoolExecutor(max_workers=2) as grupo:
        resultados = list(grupo.map(lambda _: a.busqueda.preparar(a.actor, a.version), range(2)))
    assert resultados[0] == resultados[1]
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(GeneracionBusqueda)) == 1


@pytest.mark.parametrize("tabla", ["generacion_busqueda_lista", "registro_busqueda_lista", "termino_busqueda_lista"])
def test_f62_sql_impide_modificar_o_borrar_derivados_listos(busqueda, tabla):
    busqueda.busqueda.preparar(busqueda.actor, busqueda.version)
    asignacion = "huella='" + "b" * 64 + "'" if tabla != "termino_busqueda_lista" else "ordinal=ordinal+100"
    for sentencia in [f"UPDATE {tabla} SET {asignacion}", f"DELETE FROM {tabla}"]:
        with pytest.raises(DBAPIError, match="inmutable"), busqueda.sesiones.begin() as sesion:
            sesion.execute(text(sentencia))


def test_f62_sql_no_confirma_generacion_parcial(busqueda):
    a = busqueda
    with pytest.raises(DBAPIError, match="incompleta"), a.sesiones.begin() as sesion:
        sesion.add(GeneracionBusqueda(version_id=a.version, adaptador_version="ensayo-parcial",
            normalizacion_version="v1", catalogo_huella="a"*64, estado="PREPARANDO",
            cantidad_registros=2, cantidad_consultables=0, huella="a"*64))


def test_f62_fijada_incompatible_o_bloqueada_no_se_sustituye(busqueda):
    a = busqueda
    generacion = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    fijada = fijar(a, generacion)
    with pytest.raises(ErrorIntegridadEvidencia), a.sesiones.begin() as sesion:
        a.busqueda.leer_fijada(sesion, fijada.model_copy(update={"generacion_hash": "b"*64}))
    from infrastructure.persistencia.repositorios.administracion_listas import RepositorioAdministracionListas
    incidentes = ActorListas.desde_identidad_validada(a.actor.issuer, "incidentes", ("listas_incidentes",))
    RepositorioAdministracionListas(a.sesiones, a.busqueda.politica, a.custodia, lambda *_: None).bloquear(incidentes, a.version, "Bloqueo sintético")
    with pytest.raises(VersionNoDisponible):
        fijar(a, generacion)
    with pytest.raises(VersionNoDisponible), a.sesiones.begin() as sesion:
        a.busqueda.leer_fijada(sesion, fijada)


def test_f62_integridad_detecta_alteracion_privilegiada(busqueda, administracion_bd):
    a = busqueda
    generacion = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    fijada = fijar(a, generacion)
    # Como propietario, simula corrupción que la cuenta de aplicación no puede producir.
    with administracion_bd.begin() as conexion:
        conexion.execute(text("ALTER TABLE termino_busqueda_lista DISABLE TRIGGER proteger_derivado"))
        conexion.execute(text("UPDATE termino_busqueda_lista SET huella_valor=:huella"), {"huella": "c"*64})
        conexion.execute(text("ALTER TABLE termino_busqueda_lista ENABLE TRIGGER proteger_derivado"))
    with pytest.raises(ErrorIntegridadEvidencia, match="Índice"), a.sesiones.begin() as sesion:
        a.busqueda.leer_fijada(sesion, fijada)


def test_f62_sesion_preexistente_no_oculta_bloqueo(busqueda):
    from infrastructure.persistencia.repositorios.administracion_listas import RepositorioAdministracionListas
    a = busqueda
    generacion = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    fijada = fijar(a, generacion)
    incidentes = ActorListas.desde_identidad_validada(a.actor.issuer, "incidentes", ("listas_incidentes",))
    with a.sesiones.begin() as sesion:
        # Conservar la referencia impide que el mapa de identidad descarte el objeto.
        version_previa = sesion.get(VersionFuente, a.version)
        assert version_previa.estado == "VALIDA"
        RepositorioAdministracionListas(a.sesiones, a.busqueda.politica, a.custodia, lambda *_: None).bloquear(incidentes, a.version, "Bloqueo posterior a la lectura")
        with pytest.raises(VersionNoDisponible):
            a.busqueda.leer_fijada(sesion, fijada)


def test_f62_cambio_activo_no_mezcla_versiones(busqueda):
    from .test_importacion_f54 import preparar, importador
    a = busqueda
    primera = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    fijada = fijar(a, primera)
    identidad(a)
    preparar(a, "v2.xml")
    assert importador(a).ejecutar_uno()
    with a.sesiones() as sesion:
        nueva = sesion.scalar(select(VersionFuente).where(VersionFuente.id != a.version)).id
    segunda = a.busqueda.preparar(a.actor, nueva)
    comparacion = comparar(a, nueva, 1, "comparacion-nueva")
    solicitud = solicitar(a, comparacion, clave="solicitud-nueva")
    identidad(a, "revisor", ("listas_aprobador",))
    aprobacion = decidir(a, solicitud, clave="aprobacion-nueva").json()["revision_id"]
    lista_para_cambiar, permitir_cambio = Event(), Event()
    def cambiar():
        lista_para_cambiar.set()
        permitir_cambio.wait(5)
        respuesta = ejecutar(a, solicitud, aprobacion, 1, "ejecucion-nueva")
        assert respuesta.status_code == 200, respuesta.text
    with ThreadPoolExecutor(max_workers=1) as grupo:
        with a.sesiones.begin() as sesion:
            assert a.busqueda.fijar_activas(sesion, {"ofac_sdn_prueba": primera})[0] == fijada
            tarea = grupo.submit(cambiar)
            assert lista_para_cambiar.wait(5)
            permitir_cambio.set()
            # El cambio necesita el puntero bloqueado por esta admisión.
            assert sesion.get(FuenteVersionActiva, a.fuente).version_id == a.version
        tarea.result(timeout=10)
    with pytest.raises(VersionNoDisponible):
        fijar(a, primera)
    assert fijar(a, segunda).version_id == nueva
    with a.sesiones.begin() as sesion:
        assert all(r.referencia.version_id == a.version for r in a.busqueda.leer_fijada(sesion, fijada).registros)


def test_f62_sigkill_no_deja_generacion_visible_y_reinicia(busqueda, tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    import time
    a = busqueda
    senal, opciones = tmp_path / "senal", tmp_path / "opciones.json"
    opciones.write_text(json.dumps({"version": str(a.version), "custodia": str(a.custodia.directorio), "senal": str(senal)}))
    with (tmp_path / "proceso.log").open("w+") as salida:
        proceso = subprocess.Popen([sys.executable, "-m", "tests.persistencia_listas.proceso_busqueda_sintetica", str(opciones)], stdout=salida, stderr=salida)
        try:
            limite = time.monotonic() + 10
            while not senal.exists() and proceso.poll() is None and time.monotonic() < limite:
                time.sleep(0.05)
            salida.flush()
            assert senal.exists(), (tmp_path / "proceso.log").read_text()
            with a.sesiones() as sesion:
                assert sesion.scalar(select(func.count()).select_from(GeneracionBusqueda)) == 0
            proceso.kill()
            assert proceso.wait(timeout=5) == -9
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait(timeout=5)
    with a.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(RegistroBusquedaPersistido)) == 0
        assert sesion.scalar(select(func.count()).select_from(TerminoBusqueda)) == 0
    assert a.busqueda.preparar(a.actor, a.version)


def test_f62_cambio_catalogo_exige_nueva_generacion(busqueda):
    a = busqueda
    anterior = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    a.busqueda.catalogo = a.busqueda.catalogo.model_copy(update={"version": "ensayo-v2"})
    with pytest.raises(VersionNoDisponible, match="receta"):
        fijar(a, anterior)
    nueva = a.busqueda.preparar(a.actor, a.version)
    assert nueva != anterior
    assert fijar(a, nueva).generacion_id == nueva


def test_f62_ofac_ficticio_prepara_relaciones_y_excluye_transporte(carga, monkeypatch):
    from lxml import etree
    from infrastructure.persistencia.modelos_listas import FuenteLista
    from .test_ofac_archivos import metadatos, FIJO
    from services.listas.validacion_archivos import TrabajadorValidacionArchivos
    from services.listas.importacion_archivos import TrabajadorImportacionArchivos
    from .test_recepcion_f52 import BASE
    monkeypatch.setenv("LISTAS_OFAC_LOCAL_HABILITADA", "true")
    arbol = etree.parse(str(FIJO))
    arbol.xpath('//*[local-name()="Profile"]')[0].set("PartySubTypeID", "1")
    contenido = etree.tostring(arbol)
    with carga.sesiones.begin() as sesion:
        sesion.add(FuenteLista(codigo="ofac_sdn", nombre="OFAC ficticio", organismo="Pruebas", url_oficial="FIXTURE_LOCAL"))
    respuesta = carga.cliente.post(BASE, json=metadatos(contenido), headers={"Idempotency-Key": "ofac-f62"})
    assert respuesta.status_code == 201, respuesta.text
    recepcion = respuesta.json()["recepcion_id"]
    assert carga.cliente.put(BASE + "/" + recepcion + "/contenido", content=contenido, headers={"Content-Type": "application/octet-stream"}).status_code == 202
    assert TrabajadorValidacionArchivos(carga.sesiones, carga.custodia, "development", True).ejecutar_uno()
    assert TrabajadorImportacionArchivos(carga.sesiones, carga.custodia, "development", True).ejecutar_uno()
    with carga.sesiones() as sesion:
        version = sesion.scalar(select(VersionFuente))
        version_id = version.id
    politica = PoliticaListasV2(carga.app.state.config.listas_cautela, "development")
    actor = ActorListas.desde_identidad_validada(carga.app.state.config.keycloak.issuer, "operador-local", ("listas_cargador",))
    repositorio = RepositorioBusquedaListas(carga.sesiones, carga.custodia, politica,
        CatalogoPreparacion(version="ensayo-v1", identificadores=IDENTIFICADORES_INICIALES))
    identificador = repositorio.preparar(actor, version_id)
    with carga.sesiones() as sesion:
        generacion = sesion.get(GeneracionBusqueda, identificador)
        assert generacion.cantidad_registros == 2 and generacion.cantidad_consultables == 1
        filas = repositorio._verificar(sesion, generacion)
        assert sum(f.motivo_exclusion == "TIPO_FUERA_DEL_ALCANCE" for f in filas) == 1
        registro = next(f.datos["registro"] for f in filas if f.datos)
        assert registro["tipo_sujeto"] == "ENTIDAD" and registro["identificadores"][0]["valor"] == "00001232"


def test_f62_modelos_coinciden_con_migracion(administracion_bd):
    from sqlalchemy import inspect
    from infrastructure.persistencia.modelos_busqueda_listas import TABLAS_BUSQUEDA
    inspector = inspect(administracion_bd)
    for tabla in TABLAS_BUSQUEDA:
        columnas = {c["name"]: c for c in inspector.get_columns(tabla.name)}
        assert set(columnas) == set(tabla.columns.keys())
        assert all(columnas[c.name]["nullable"] == c.nullable for c in tabla.columns)
        nombres_fk = {f["name"] for f in inspector.get_foreign_keys(tabla.name)}
        assert {f.name for f in tabla.foreign_key_constraints if f.name} <= nombres_fk
        nombres_indices = {i["name"] for i in inspector.get_indexes(tabla.name)}
        assert {i.name for i in tabla.indexes} <= nombres_indices


def test_f62_migracion_revierte_solo_derivados_y_reaplica(sesiones, administracion_bd):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import inspect
    configuracion = Config(str(Path(__file__).parents[2] / "backend/alembic.ini"))
    with administracion_bd.connect() as conexion:
        assert conexion.scalar(text("SELECT version_num FROM alembic_version")) == "j10e23f456a7"
    command.downgrade(configuracion, "h98c01d234e5")
    inspector = inspect(administracion_bd)
    assert "generacion_busqueda_lista" not in inspector.get_table_names()
    assert "version_fuente" in inspector.get_table_names() and "consulta_lista" in inspector.get_table_names()
    command.upgrade(configuracion, "head")
    assert "generacion_busqueda_lista" in inspect(administracion_bd).get_table_names()
    # Los permisos del fixture se restauran para las pruebas siguientes, solo en /tmp.
    with administracion_bd.begin() as conexion:
        conexion.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON generacion_busqueda_lista, registro_busqueda_lista, termino_busqueda_lista TO aplicacion_listas"))
