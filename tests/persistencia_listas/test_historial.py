"""Pruebas de F2 sobre PostgreSQL y objetos locales, sin listas reales ni API externa."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pypdf import PdfReader
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import DBAPIError

from domain.listas.contratos import CrearConsultaV2, SolicitudIdempotente
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia, TrabajoNoVigente, VersionNoDisponible
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.listas.simulado import SimuladorListasV2
from infrastructure.persistencia.modelos_listas import (
    ArchivoFuente, BorradorConsulta, CoincidenciaLista, ConsultaFuente, ConsultaLista, EventoActivacion,
    EvidenciaConsulta, FuenteVersionActiva, RecepcionFuente, RegistroLista, RevisionCumplimiento,
    TrabajoConsulta, VersionFuente,
)
from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
from services.listas.consulta_v2 import EjecutorConsultaV2
from services.listas.politica_v2 import PoliticaListasV2
from .conftest import RAIZ, activar_version, crear_version, preparar_comparacion


def peticion(clave="consulta-1", nombre="Persona ficticia"):
    return SolicitudIdempotente(clave=clave, solicitud=CrearConsultaV2(
        version_contrato="2.0", contexto={"tipo": "INDEPENDIENTE", "motivo": "Prueba de historial local"},
        criterio={"tipo_sujeto": "PERSONA", "nombre": nombre}))


def admitir(escenario, clave="consulta-1"):
    return escenario.consultas.admitir(escenario.cargador, peticion(clave), "simulador", {"escenario": "sin_coincidencias_v1"})


def guardar_resultado(escenario, consulta_id, nombre_escenario="sin_coincidencias_v1"):
    concesion = escenario.consultas.reclamar(consulta_id)
    ejecutor = EjecutorConsultaV2(escenario.politica, SimuladorListasV2(nombre_escenario), lambda *_: True)
    resultado = ejecutor.consultar(escenario.cargador, peticion().solicitud, consulta_id, uuid4())
    escenario.consultas.guardar_borrador(concesion, resultado)
    return concesion


def cerrar_consulta(escenario, clave="consulta-1", nombre_escenario="sin_coincidencias_v1"):
    consulta_id = admitir(escenario, clave)
    concesion = guardar_resultado(escenario, consulta_id, nombre_escenario)
    escenario.consultas.preparar_informe(concesion)
    evidencia_id = escenario.consultas.cerrar(concesion)
    return consulta_id, evidencia_id


def test_migracion_completa_crea_restricciones_y_aplicacion_no_es_propietaria(escenario, administracion_bd):
    inspector = inspect(administracion_bd)
    assert "consulta_lista" in inspector.get_table_names()
    assert len(inspector.get_foreign_keys("coincidencia_lista")) >= 4
    with escenario.sesiones() as sesion:
        assert sesion.execute(text("SELECT current_user")).scalar_one() == "aplicacion_listas"
        configuracion = Config(str(RAIZ / "backend/alembic.ini"))
        assert sesion.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == ScriptDirectory.from_config(configuracion).get_current_head()
        assert sesion.get(FuenteVersionActiva, escenario.fuente).revision == 0


def test_custodia_no_sobrescribe_detecta_corrupcion_y_rechaza_rutas(tmp_path):
    custodia = CustodiaLocalListas(tmp_path / "custodia")
    objeto = custodia.guardar(b"evidencia original")
    assert custodia.guardar(b"evidencia original") == objeto
    assert custodia.leer(objeto.clave, objeto.huella) == b"evidencia original"
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.leer("../../otro", "a" * 64)
    (custodia.directorio / objeto.clave).write_bytes(b"alteracion externa")
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.leer(objeto.clave, objeto.huella)
    with pytest.raises(ErrorIntegridadEvidencia):
        custodia.guardar(b"evidencia original")


def test_primera_activacion_reintento_y_conflicto_de_cuerpo(escenario):
    version, _ = crear_version(escenario)
    comparacion, aprobacion = preparar_comparacion(escenario, version)
    evento = activar_version(escenario, comparacion, aprobacion)
    assert evento == activar_version(escenario, comparacion, aprobacion)
    assert evento.revision == 1
    with pytest.raises(ConflictoListas):
        activar_version(escenario, comparacion, aprobacion, revision=1)
    with escenario.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EventoActivacion)) == 1


def test_dos_activaciones_simultaneas_solo_una_gana(escenario):
    primera, _ = crear_version(escenario)
    segunda, _ = crear_version(escenario, "version-2")
    comparaciones = [preparar_comparacion(escenario, v) for v in (primera, segunda)]
    barrera = Barrier(2)

    def activar(indice):
        barrera.wait()
        try:
            return activar_version(escenario, *comparaciones[indice], clave=f"activacion-{indice}")
        except ConflictoListas:
            return None

    with ThreadPoolExecutor(max_workers=2) as ejecutores:
        resultados = list(ejecutores.map(activar, (0, 1)))
    assert sum(r is not None for r in resultados) == 1


def test_dos_reintentos_simultaneos_devuelven_el_mismo_evento(escenario):
    version, _ = crear_version(escenario)
    comparacion, aprobacion = preparar_comparacion(escenario, version)
    barrera = Barrier(2)

    def activar(_):
        barrera.wait()
        return activar_version(escenario, comparacion, aprobacion)

    with ThreadPoolExecutor(max_workers=2) as ejecutores:
        resultados = list(ejecutores.map(activar, (0, 1)))
    assert resultados[0] == resultados[1]


def test_reversion_exige_comparacion_nueva_y_aba_detecta_revision(escenario):
    primera, _ = crear_version(escenario)
    segunda, _ = crear_version(escenario, "version-2")
    activar_version(escenario, *preparar_comparacion(escenario, primera))
    comparacion_vieja = preparar_comparacion(escenario, segunda, primera, 1)
    activar_version(escenario, *comparacion_vieja, revision=1, clave="cambio-2")
    activar_version(escenario, *preparar_comparacion(escenario, primera, segunda, 2), revision=2, clave="reversion", tipo="REVERSION")
    with pytest.raises(ConflictoListas):
        activar_version(escenario, *comparacion_vieja, revision=1, clave="aprobacion-vieja")
    with escenario.sesiones() as sesion:
        puntero = sesion.get(FuenteVersionActiva, escenario.fuente)
        assert puntero.version_id == primera and puntero.revision == 3


def test_aprobacion_revocada_no_activa(escenario):
    version, _ = crear_version(escenario)
    comparacion, aprobacion = preparar_comparacion(escenario, version)
    escenario.catalogo.revocar(escenario.aprobador, aprobacion, "Se requiere otra revisión")
    with pytest.raises(ConflictoListas):
        activar_version(escenario, comparacion, aprobacion)
    with escenario.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva, escenario.fuente).version_id is None


def test_version_bloqueada_no_se_activa(escenario):
    version, _ = crear_version(escenario)
    comparacion, aprobacion = preparar_comparacion(escenario, version)
    escenario.catalogo.bloquear(escenario.aprobador, version, "Integridad cuestionada")
    with pytest.raises(VersionNoDisponible):
        activar_version(escenario, comparacion, aprobacion)


@pytest.mark.parametrize("tabla,campo,valor", [
    ("version_fuente", "cantidad_registros", "2"),
    ("registro_lista", "uid_original", "'alterado'"),
    ("recepcion_fuente", "actor_sujeto", "'otro'"),
    ("archivo_fuente", "huella", "'b'"),
])
def test_sql_directo_no_altera_version_ni_procedencia(escenario, tabla, campo, valor):
    crear_version(escenario)
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(text(f"UPDATE {tabla} SET {campo}={valor}"))


def test_puntero_no_cambia_sin_evento_transaccional(escenario):
    version, _ = crear_version(escenario)
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(update(FuenteVersionActiva).values(version_id=version, revision=1))
    with escenario.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva, escenario.fuente).revision == 0


def test_idempotencia_durable_y_doble_admision(escenario):
    barrera = Barrier(2)

    def crear(_):
        barrera.wait()
        return admitir(escenario)

    with ThreadPoolExecutor(max_workers=2) as ejecutores:
        resultados = list(ejecutores.map(crear, (0, 1)))
    assert resultados[0] == resultados[1]
    with escenario.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 1
        assert sesion.scalar(select(func.count()).select_from(TrabajoConsulta)) == 1
    with pytest.raises(ConflictoListas):
        escenario.consultas.admitir(escenario.cargador, peticion(nombre="Otra persona"), "simulador", {})


def test_concesion_vencida_no_escribe_y_reanuda_borrador(escenario):
    consulta_id = admitir(escenario)
    vieja = guardar_resultado(escenario, consulta_id)
    with pytest.raises(TrabajoNoVigente):
        escenario.consultas.reclamar(consulta_id)
    escenario.reloj[0] += timedelta(seconds=121)
    nueva = escenario.consultas.reclamar(consulta_id)
    assert nueva.numero_control == vieja.numero_control + 1
    assert nueva.fase == "PREPARANDO_EVIDENCIA"
    with pytest.raises(TrabajoNoVigente):
        escenario.consultas.renovar(vieja)
    escenario.consultas.preparar_informe(nueva)
    escenario.consultas.cerrar(nueva)


def test_pdf_real_y_consulta_historica_no_reconsulta(escenario):
    consulta_id, _ = cerrar_consulta(escenario)
    contenido = escenario.consultas.leer_informe(escenario.cargador, consulta_id)
    lector = PdfReader(BytesIO(contenido))
    assert "Informe de consulta" in lector.pages[0].extract_text()
    assert "Persona ficticia" in "".join(p.extract_text() for p in lector.pages)
    escenario.consultas.politica = PoliticaListasV2(SagrilaftListasConfig(proveedor="deshabilitado", implementacion=None), "development")
    assert escenario.consultas.leer_informe(escenario.cargador, consulta_id) == contenido
    escenario.consultas.puede_acceder_consulta = lambda *_: False
    with pytest.raises(PermissionError):
        escenario.consultas.leer_informe(escenario.cargador, consulta_id)


@pytest.mark.parametrize("tabla", ["consulta_lista", "coincidencia_lista", "evidencia_consulta", "borrador_consulta", "consulta_fuente"])
def test_historial_cerrado_no_se_borra_por_sql(escenario, tabla):
    cerrar_consulta(escenario, nombre_escenario="coincidencia_v1")
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(text(f"DELETE FROM {tabla}"))


def test_fallo_almacen_no_cierra_y_reintenta_sin_consultar(escenario, monkeypatch):
    consulta_id = admitir(escenario)
    concesion = guardar_resultado(escenario, consulta_id)
    guardar = escenario.custodia.guardar

    def fallar(_):
        raise OSError("Fallo de disco inyectado")

    monkeypatch.setattr(escenario.custodia, "guardar", fallar)
    with pytest.raises(OSError):
        escenario.consultas.preparar_informe(concesion)
    with escenario.sesiones() as sesion:
        assert sesion.get(ConsultaLista, consulta_id).estado == "EN_CURSO"
        assert sesion.scalar(select(func.count()).select_from(EvidenciaConsulta)) == 0
    monkeypatch.setattr(escenario.custodia, "guardar", guardar)
    escenario.consultas.preparar_informe(concesion)
    escenario.consultas.cerrar(concesion)


def test_revisiones_son_aditivas_y_no_cruzan_consultas(escenario):
    consulta_id, _ = cerrar_consulta(escenario, nombre_escenario="coincidencia_v1")
    otra, _ = cerrar_consulta(escenario, "otra")
    with escenario.sesiones() as sesion:
        coincidencia = sesion.scalar(select(CoincidenciaLista.id).where(CoincidenciaLista.consulta_id == consulta_id))
    primera = escenario.consultas.revisar(escenario.cargador, consulta_id, "REQUIERE_INFORMACION", "Identidad por verificar", coincidencia)
    escenario.consultas.revisar(escenario.cargador, consulta_id, "DESCARTADA", "La documentación aclara el homónimo", coincidencia, primera)
    with pytest.raises(DBAPIError):
        escenario.consultas.revisar(escenario.cargador, otra, "DESCARTADA", "Intento cruzado", coincidencia)
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(update(RevisionCumplimiento).values(justificacion="reescritura"))


def test_no_se_cierra_exito_sin_informe(escenario):
    consulta_id = admitir(escenario)
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(update(ConsultaLista).where(ConsultaLista.id == consulta_id).values(
            estado="COMPLETADA", conclusion="SIN_CANDIDATOS", finalizada_en=escenario.reloj[0], resultado={}))


def test_downgrade_con_datos_es_rechazado(escenario):
    with pytest.raises(RuntimeError, match="preservar el historial"):
        command.downgrade(Config(str(RAIZ / "backend/alembic.ini")), "f8a9b0c1d2e3")


def repositorio_archivos(escenario):
    politica = PoliticaListasV2(SagrilaftListasConfig(proveedor=None, implementacion="archivos", admin_habilitada=True,
                                                   independiente_habilitada=True), "development")
    return RepositorioConsultasListas(escenario.sesiones, politica, escenario.custodia, lambda *_: True, lambda *_: True,
                                     escenario.verificar_vigencia, reloj=lambda: escenario.reloj[0])


def resultado_archivos(escenario, consulta_id, registro_id):
    from domain.listas.contratos import ResultadoProveedorV2, Cobertura, Candidato, Motivo
    with escenario.sesiones() as sesion:
        fijada = sesion.scalar(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta_id))
        return ResultadoProveedorV2(consulta_id=consulta_id, implementacion="archivos", proveedor="archivos-local",
            estado_ejecucion="COMPLETADA", conclusion_busqueda="CON_CANDIDATOS",
            fecha_inicio=escenario.reloj[0], fecha_fin=escenario.reloj[0],
            cobertura=(Cobertura(id=fijada.id, fuente_codigo="fuente_sintetica", nombre_origen="Lista ficticia",
                version_id=fijada.version_id, hash_contenido=fijada.detalle["huella_contenido"], revision_activa=fijada.revision_activa,
                estado="CONSULTADA"),),
            candidatos=(Candidato(id=uuid4(), cobertura_id=fijada.id, registro_id=registro_id, uid_origen="persona-ficticia-1",
                tipo_sujeto="PERSONA", nombre_principal="Persona ficticia", algoritmo_version="fixture-v1",
                motivos=(Motivo(campo="nombre", valor_consultado="Persona ficticia", valor_registro="Persona ficticia", metodo="EXACTO_NOMBRE"),)),))


def admitir_archivos(escenario, repositorio, clave="consulta-archivos"):
    return repositorio.admitir(escenario.cargador, peticion(clave), "archivos-local", {"solo_pruebas": True},
                               (escenario.fuente,), escenario.politica_id)


def test_consulta_fija_version_anterior_y_preserva_evidencia_tras_reversion(escenario):
    primera, registro = crear_version(escenario)
    activar_version(escenario, *preparar_comparacion(escenario, primera))
    repositorio = repositorio_archivos(escenario)
    consulta_id = admitir_archivos(escenario, repositorio)
    concesion = repositorio.reclamar(consulta_id)
    resultado = resultado_archivos(escenario, consulta_id, registro)
    segunda, _ = crear_version(escenario, "segunda")
    activar_version(escenario, *preparar_comparacion(escenario, segunda, primera, 1), revision=1, clave="segunda")
    repositorio.guardar_borrador(concesion, resultado)
    repositorio.preparar_informe(concesion)
    repositorio.cerrar(concesion)
    evidencia = repositorio.leer_informe(escenario.cargador, consulta_id)
    activar_version(escenario, *preparar_comparacion(escenario, primera, segunda, 2), revision=2, clave="restaurar", tipo="REVERSION")
    assert repositorio.leer_informe(escenario.cargador, consulta_id) == evidencia
    with escenario.sesiones() as sesion:
        assert sesion.scalar(select(ConsultaFuente.version_id).where(ConsultaFuente.consulta_id == consulta_id)) == primera
        assert sesion.get(ConsultaLista, consulta_id).estado == "COMPLETADA"


def test_bloqueo_durante_consulta_impide_publicar_informe_limpio(escenario):
    version, registro = crear_version(escenario)
    activar_version(escenario, *preparar_comparacion(escenario, version))
    repositorio = repositorio_archivos(escenario)
    consulta_id = admitir_archivos(escenario, repositorio)
    concesion = repositorio.reclamar(consulta_id)
    repositorio.guardar_borrador(concesion, resultado_archivos(escenario, consulta_id, registro))
    repositorio.preparar_informe(concesion)
    escenario.catalogo.bloquear(escenario.aprobador, version, "Incidencia de integridad")
    with pytest.raises(VersionNoDisponible):
        repositorio.cerrar(concesion)
    repositorio.fallar(concesion, "VERSION_BLOQUEADA")
    with escenario.sesiones() as sesion:
        assert sesion.get(ConsultaLista, consulta_id).conclusion == "NO_CONCLUYENTE"
        assert sesion.scalar(select(func.count()).select_from(EvidenciaConsulta)) == 0


def test_sin_version_activa_conserva_fallo_autorizado(escenario):
    repositorio = repositorio_archivos(escenario)
    consulta_id = admitir_archivos(escenario, repositorio)
    with escenario.sesiones() as sesion:
        consulta = sesion.get(ConsultaLista, consulta_id)
        assert consulta.estado == "FALLIDA" and consulta.conclusion == "NO_CONCLUYENTE"
    with pytest.raises(TrabajoNoVigente):
        repositorio.reclamar(consulta_id)


def test_fk_compuesta_impide_coincidencia_en_version_distinta_incluso_nula(escenario):
    primera, _ = crear_version(escenario)
    segunda, otro_registro = crear_version(escenario, "segunda")
    activar_version(escenario, *preparar_comparacion(escenario, primera))
    consulta_id = admitir_archivos(escenario, repositorio_archivos(escenario))
    with escenario.sesiones() as sesion:
        cobertura_id = sesion.scalar(select(ConsultaFuente.id).where(ConsultaFuente.consulta_id == consulta_id))
    for version_id, registro_id in ((segunda, otro_registro), (None, None)):
        with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
            sesion.add(CoincidenciaLista(consulta_id=consulta_id, consulta_fuente_id=cobertura_id, version_id=version_id,
                                        registro_id=registro_id, datos_candidato={"falso": True}))


def test_fallo_sql_al_cerrar_revierte_resultado_y_reutiliza_pdf(escenario, monkeypatch):
    consulta_id = admitir(escenario)
    concesion = guardar_resultado(escenario, consulta_id)
    original = escenario.consultas.preparar_informe(concesion)
    emitir_evento = escenario.consultas._evento

    def fallar_evento(*_):
        raise RuntimeError("Fallo inyectado antes del commit")

    monkeypatch.setattr(escenario.consultas, "_evento", fallar_evento)
    with pytest.raises(RuntimeError, match="inyectado"):
        escenario.consultas.cerrar(concesion)
    with escenario.sesiones() as sesion:
        assert sesion.get(ConsultaLista, consulta_id).estado == "EN_CURSO"
        assert sesion.scalar(select(func.count()).select_from(EvidenciaConsulta)) == 0
    monkeypatch.setattr(escenario.consultas, "_evento", emitir_evento)
    assert escenario.consultas.preparar_informe(concesion) == original
    evidencia = escenario.consultas.cerrar(concesion)
    assert escenario.consultas.cerrar(concesion) == evidencia
    assert escenario.consultas.leer_informe(escenario.cargador, consulta_id) == original


def test_error_de_persistencia_activacion_no_se_oculta_y_revierte_puntero(escenario):
    from services.listas.politica_v2 import ActorListas
    version, _ = crear_version(escenario)
    comparacion, aprobacion = preparar_comparacion(escenario, version)
    actor_invalido = ActorListas("emisor-local", "x" * 201, escenario.aprobador.permisos)
    with pytest.raises(DBAPIError):
        escenario.catalogo.activar(actor_invalido, escenario.fuente, comparacion, aprobacion, 0,
                                  escenario.politica_id, "intento", "Prueba de error de persistencia")
    with escenario.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva, escenario.fuente).revision == 0
        assert sesion.scalar(select(func.count()).select_from(EventoActivacion)) == 0


def test_sql_no_puede_bloquear_version_sin_evento(escenario):
    version, _ = crear_version(escenario)
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(update(VersionFuente).where(VersionFuente.id == version).values(estado="BLOQUEADA"))


def test_lectura_detecta_evidencia_corrupta(escenario):
    consulta_id, evidencia_id = cerrar_consulta(escenario)
    with escenario.sesiones() as sesion:
        clave = sesion.get(EvidenciaConsulta, evidencia_id).clave
    (escenario.custodia.directorio / clave).write_bytes(b"contenido alterado")
    with pytest.raises(ErrorIntegridadEvidencia):
        escenario.consultas.leer_informe(escenario.cargador, consulta_id)


def test_revision_no_se_adelanta_al_resultado(escenario):
    consulta_id = admitir(escenario)
    with pytest.raises(ConflictoListas):
        escenario.consultas.revisar(escenario.cargador, consulta_id, "DESCARTADA", "Sin resultado todavía")


def test_esquema_congelado_coincide_con_modelos_listas(administracion_bd):
    from infrastructure.persistencia.modelos_listas import TABLAS_LISTAS
    inspector = inspect(administracion_bd)
    for tabla in TABLAS_LISTAS:
        columnas = {c["name"]: c for c in inspector.get_columns(tabla.name)}
        assert set(columnas) == set(tabla.columns.keys())
        for columna in tabla.columns:
            assert columnas[columna.name]["nullable"] == columna.nullable
        restricciones = {r["name"] for r in inspector.get_check_constraints(tabla.name)}
        esperadas = {c.name for c in tabla.constraints if c.__class__.__name__ == "CheckConstraint"}
        assert restricciones == esperadas


def test_informe_no_se_reescribe_con_nuevo_generador(escenario, monkeypatch):
    consulta_id, _ = cerrar_consulta(escenario)
    anterior = escenario.consultas.leer_informe(escenario.cargador, consulta_id)
    monkeypatch.setattr(escenario.consultas, "generar_informe", lambda _: pytest.fail("No se debe regenerar al leer"))
    assert escenario.consultas.leer_informe(escenario.cargador, consulta_id) == anterior


def test_desconocimiento_de_version_externa_no_inventa_fuente_local(escenario):
    from domain.listas.contratos import ResultadoProveedorV2, Cobertura
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="externo", independiente_habilitada=True)
    repositorio = RepositorioConsultasListas(escenario.sesiones, PoliticaListasV2(configuracion, "development"),
        escenario.custodia, lambda *_: True, lambda *_: True, escenario.verificar_vigencia, reloj=lambda: escenario.reloj[0])
    consulta_id = repositorio.admitir(escenario.cargador, peticion(), "proveedor-sintetico", {"solo_pruebas": True})
    concesion = repositorio.reclamar(consulta_id)
    resultado = ResultadoProveedorV2(consulta_id=consulta_id, implementacion="externo", proveedor="proveedor-sintetico",
        estado_ejecucion="INDETERMINADA", conclusion_busqueda="NO_CONCLUYENTE",
        fecha_inicio=escenario.reloj[0], fecha_fin=escenario.reloj[0],
        cobertura=(Cobertura(id=uuid4(), nombre_origen="Cobertura desconocida", estado="DESCONOCIDA"),))
    repositorio.guardar_borrador(concesion, resultado)
    repositorio.preparar_informe(concesion)
    repositorio.cerrar(concesion)
    with escenario.sesiones() as sesion:
        cobertura = sesion.scalar(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta_id))
        assert cobertura.version_id is None and cobertura.version_externa is None and cobertura.fuente_id is None


def test_sql_no_puede_usar_una_version_inactiva(escenario):
    primera, _ = crear_version(escenario)
    segunda, _ = crear_version(escenario, "segunda")
    activar_version(escenario, *preparar_comparacion(escenario, primera))
    consulta_id = admitir_archivos(escenario, repositorio_archivos(escenario))
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.add(ConsultaFuente(consulta_id=consulta_id, fuente_id=escenario.fuente, version_id=segunda,
                                 revision_activa=1, nombre_origen="Candidata inactiva", estado="PENDIENTE"))


def test_aplicacion_no_puede_desactivar_disparadores(escenario):
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(text("ALTER TABLE consulta_lista DISABLE TRIGGER ALL"))


def test_historial_devuelve_copia_y_exige_acceso(escenario, monkeypatch):
    consulta_id, evidencia_id = cerrar_consulta(escenario)
    historia = escenario.consultas.obtener_consulta(escenario.cargador, consulta_id)
    assert historia["estado"] == "COMPLETADA"
    assert historia["evidencias"][0]["id"] == str(evidencia_id)
    assert "clave" not in historia["evidencias"][0]
    historia["criterio_original"]["nombre"] = "Cambio fuera de la sesión"
    assert escenario.consultas.obtener_consulta(escenario.cargador, consulta_id)["criterio_original"]["nombre"] == "Persona ficticia"
    monkeypatch.setattr(escenario.consultas, "puede_acceder_consulta", lambda *_: False)
    with pytest.raises(PermissionError):
        escenario.consultas.obtener_consulta(escenario.cargador, consulta_id)
    with pytest.raises(PermissionError):
        escenario.consultas.leer_informe(escenario.cargador, consulta_id)


def test_concesion_externa_vencida_finaliza_sin_repetir_llamada(escenario):
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="externo", independiente_habilitada=True)
    repositorio = RepositorioConsultasListas(escenario.sesiones, PoliticaListasV2(configuracion, "development"),
        escenario.custodia, lambda *_: True, lambda *_: True, escenario.verificar_vigencia, reloj=lambda: escenario.reloj[0])
    consulta_id = repositorio.admitir(escenario.cargador, peticion(), "proveedor-ficticio", {})
    antigua = repositorio.reclamar(consulta_id, 1)
    escenario.reloj[0] += timedelta(seconds=2)
    assert repositorio.reclamar(consulta_id) is None
    historia = repositorio.obtener_consulta(escenario.cargador, consulta_id)
    assert historia["estado"] == "INDETERMINADA" and historia["conclusion"] == "NO_CONCLUYENTE"
    assert historia["evidencias"] == []
    with pytest.raises(TrabajoNoVigente):
        repositorio.renovar(antigua)


def test_historial_expediente_preserva_reconsultas_y_restringe_acceso(escenario, monkeypatch):
    from services.listas.politica_v2 import ActorListas
    expediente_id = str(uuid4())
    with escenario.sesiones.begin() as sesion:
        sesion.execute(text("INSERT INTO formularios(id) VALUES (:id)"), {"id": expediente_id})
    actor = ActorListas(escenario.cargador.issuer, escenario.cargador.sub, escenario.cargador.permisos | {"listas.consultar"})
    for clave in ("primera", "segunda"):
        solicitud = SolicitudIdempotente(clave=clave, solicitud=CrearConsultaV2(version_contrato="2.0",
            contexto={"tipo": "EXPEDIENTE", "expediente_id": expediente_id, "sujeto_rol": "CONTRAPARTE"},
            criterio={"tipo_sujeto": "PERSONA", "nombre": "Persona ficticia"}))
        escenario.consultas.admitir(actor, solicitud, "simulador", {})
    historia = escenario.consultas.listar_historial_expediente(actor, expediente_id)
    assert len(historia) == 2 and historia[0]["consulta_id"] != historia[1]["consulta_id"]
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(text("DELETE FROM formularios WHERE id=:id"), {"id": expediente_id})
    monkeypatch.setattr(escenario.consultas, "puede_acceder_expediente", lambda *_: False)
    with pytest.raises(PermissionError):
        escenario.consultas.listar_historial_expediente(actor, expediente_id)


def test_aplicacion_no_puede_truncar_historial(escenario):
    with pytest.raises(DBAPIError), escenario.sesiones.begin() as sesion:
        sesion.execute(text("TRUNCATE consulta_lista CASCADE"))


def test_downgrade_vacio_y_reaplicacion(sesiones, administracion_bd):
    configuracion = Config(str(RAIZ / "backend/alembic.ini"))
    command.downgrade(configuracion, "f8a9b0c1d2e3")
    assert "consulta_lista" not in inspect(administracion_bd).get_table_names()
    command.upgrade(configuracion, "head")
    # Reponer las concesiones del rol de prueba sobre las tablas recién creadas.
    with administracion_bd.begin() as conexion:
        conexion.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aplicacion_listas"))
    assert "consulta_lista" in inspect(administracion_bd).get_table_names()


@pytest.mark.parametrize("primero", ["activacion", "revocacion"])
def test_activacion_y_revocacion_concurrentes_respetan_orden(escenario, primero):
    from threading import Event
    from sqlalchemy import event
    from infrastructure.persistencia.modelos_listas import ComparacionVersion, RevisionComparacion

    version, _ = crear_version(escenario)
    comparacion_id, aprobacion_id = preparar_comparacion(escenario, version)
    intento_bloqueo = Event()
    motor = escenario.sesiones.kw["bind"]

    def detectar_bloqueo(_conexion, _cursor, sentencia, _parametros, _contexto, _multiples):
        if "FROM comparacion_version" in sentencia and "FOR UPDATE" in sentencia:
            intento_bloqueo.set()

    def activar():
        return activar_version(escenario, comparacion_id, aprobacion_id)

    if primero == "revocacion":
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            with escenario.sesiones.begin() as sesion:
                sesion.execute(select(ComparacionVersion).where(ComparacionVersion.id == comparacion_id).with_for_update()).scalar_one()
                sesion.add(RevisionComparacion(comparacion_id=comparacion_id, decision="REVOCADA", revoca_revision_id=aprobacion_id,
                    actor_emisor=escenario.aprobador.issuer, actor_sujeto=escenario.aprobador.sub, motivo="Revocación concurrente"))
                sesion.flush()
                event.listen(motor, "before_cursor_execute", detectar_bloqueo)
                pendiente = ejecutor.submit(activar)
                try:
                    assert intento_bloqueo.wait(3), "Activación no intentó adquirir el bloqueo"
                finally:
                    event.remove(motor, "before_cursor_execute", detectar_bloqueo)
            with pytest.raises(ConflictoListas, match="aprobación"):
                pendiente.result(timeout=5)
    else:
        activacion_bloqueada = Event()
        permitir_confirmacion = Event()
        verificar_original = escenario.catalogo.verificar_vigencia

        def verificar_y_esperar(*argumentos):
            verificar_original(*argumentos)
            activacion_bloqueada.set()
            assert permitir_confirmacion.wait(5), "No se permitió terminar la activación"

        escenario.catalogo.verificar_vigencia = verificar_y_esperar
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            pendiente = ejecutor.submit(activar)
            try:
                assert activacion_bloqueada.wait(3)
                event.listen(motor, "before_cursor_execute", detectar_bloqueo)
                revocacion = ejecutor.submit(escenario.catalogo.revocar, escenario.aprobador, aprobacion_id, "Revocación posterior")
                assert intento_bloqueo.wait(3)
            finally:
                permitir_confirmacion.set()
                event.remove(motor, "before_cursor_execute", detectar_bloqueo)
            assert pendiente.result(timeout=5).version_id == version
            revocacion.result(timeout=5)
    with escenario.sesiones() as sesion:
        puntero = sesion.get(FuenteVersionActiva, escenario.fuente)
        assert puntero.version_id == (version if primero == "activacion" else None)
