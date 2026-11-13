"""Solo admite el clúster temporal creado por probar_listas_postgres.py."""
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.persistencia.modelos_listas import (
    TABLAS_LISTAS, ArchivoFuente, ComparacionVersion, EsquemaFuente, EventoVersion,
    PoliticaListas, RecepcionFuente, RegistroLista, VersionFuente,
)
from infrastructure.persistencia.repositorios.administracion_listas import RepositorioAdministracionListas
from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
from services.listas.informes import calcular_huella
from services.listas.politica_v2 import ActorListas, PoliticaListasV2

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def administracion_bd():
    direccion = os.getenv("LISTAS_PRUEBA_URL")
    directorio = os.getenv("LISTAS_PRUEBA_DIRECTORIO")
    if not direccion or not directorio:
        pytest.skip("Ejecutar con scripts/validacion/probar_listas_postgres.py; nunca usar una BD existente")
    ruta = Path(directorio).resolve()
    url = make_url(direccion)
    assert ruta.parent == Path("/tmp") and ruta.name.startswith("listas-f2-")
    assert url.query.get("host") == str(ruta / "conexiones") and url.host is None
    assert os.getenv("DATABASE_URL") == direccion
    configuracion = Config(str(RAIZ / "backend/alembic.ini"))
    command.upgrade(configuracion, "head")
    motor = create_engine(direccion)
    with motor.begin() as conexion:
        conexion.execute(text("CREATE ROLE aplicacion_listas NOLOGIN"))
        conexion.execute(text("GRANT USAGE ON SCHEMA public TO aplicacion_listas"))
        conexion.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aplicacion_listas"))
        conexion.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aplicacion_listas"))
    yield motor
    motor.dispose()


@pytest.fixture
def sesiones(administracion_bd):
    # Limpieza exclusiva de este clúster desechable, como propietario, no como aplicación.
    with administracion_bd.begin() as conexion:
        conexion.execute(text("TRUNCATE grupo_consulta_lista," + ",".join(t.name for t in TABLAS_LISTAS) + " CASCADE"))
    motor = create_engine(os.environ["LISTAS_PRUEBA_URL"], pool_size=8)

    @event.listens_for(motor, "connect")
    def usar_rol_aplicacion(conexion, _registro):
        with conexion.cursor() as cursor:
            cursor.execute("SET ROLE aplicacion_listas")
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute("SET lock_timeout = '5s'")
        conexion.commit()

    yield sessionmaker(motor, expire_on_commit=False)
    motor.dispose()


@pytest.fixture
def escenario(sesiones, tmp_path):
    permisos = frozenset({"listas.importar", "listas.comparar", "listas.aprobar_version", "listas.activar_version", "listas.bloquear_version", "listas.consultar_independiente", "listas.ver_evidencias", "listas.revisar"})
    cargador = ActorListas("emisor-local", "cargador", permisos)
    aprobador = ActorListas("emisor-local", "aprobador", permisos)
    custodia = CustodiaLocalListas(tmp_path / "objetos")
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="simulado", escenario="sin_coincidencias_v1", admin_habilitada=True, independiente_habilitada=True)
    politica = PoliticaListasV2(configuracion, "development")
    reloj = [datetime.now(timezone.utc)]

    def verificar_vigencia(_sesion, _version, politica_guardada):
        # Política de fixtures: no constituye política de vigencia de OFAC real.
        assert politica_guardada.parametros["solo_pruebas"] is True

    catalogo = RepositorioAdministracionListas(sesiones, politica, custodia, verificar_vigencia)
    consultas = RepositorioConsultasListas(sesiones, politica, custodia, lambda *_: True, lambda *_: True,
                                          verificar_vigencia, reloj=lambda: reloj[0])
    fuente = catalogo.crear_fuente(cargador, "fuente_sintetica", "Lista de pruebas", "Equipo de pruebas", "https://fuente.test")
    politica_id = uuid4()
    with sesiones.begin() as sesion:
        sesion.add(PoliticaListas(id=politica_id, codigo="pruebas", version=1, parametros={"solo_pruebas": True},
                                 huella=calcular_huella({"solo_pruebas": True}), aprobador_emisor="emisor-local", aprobador_sujeto="aprobador"))
    return SimpleNamespace(sesiones=sesiones, cargador=cargador, aprobador=aprobador, custodia=custodia,
                           politica=politica, catalogo=catalogo, consultas=consultas, fuente=fuente,
                           politica_id=politica_id, verificar_vigencia=verificar_vigencia, reloj=reloj)


def crear_version(escenario, nombre="version-1", fuente_id=None):
    fuente_id = fuente_id or escenario.fuente
    archivo = escenario.custodia.guardar(f"Archivo ficticio: {nombre}".encode())
    version_id, registro_id = uuid4(), uuid4()
    with escenario.sesiones.begin() as sesion:
        archivo_id, esquema_id, recepcion_id = uuid4(), uuid4(), uuid4()
        sesion.add(ArchivoFuente(id=archivo_id, clave=archivo.clave, huella=archivo.huella, tamano_bytes=archivo.tamano_bytes,
                                 tipo_contenido="text/plain", nombre_recibido=nombre))
        sesion.flush()
        sesion.add(EsquemaFuente(id=esquema_id, fuente_id=fuente_id, archivo_id=archivo_id, formato="FIXTURE", version="1", aprobado=True))
        sesion.add(RecepcionFuente(id=recepcion_id, fuente_id=fuente_id, archivo_id=archivo_id, actor_emisor=escenario.cargador.issuer,
                                   actor_sujeto=escenario.cargador.sub, url_declarada="https://fuente.test", estado="RECIBIDA"))
        sesion.flush()
        version = VersionFuente(id=version_id, fuente_id=fuente_id, recepcion_id=recepcion_id, esquema_id=esquema_id,
                                archivo_raiz_id=archivo_id, archivo_contenido_id=archivo_id, formato="FIXTURE",
                                version_importador="fixture-v1", version_normalizador="fixture-v1", huella_contenido=archivo.huella)
        sesion.add(version)
        sesion.flush()
        sesion.add(RegistroLista(id=registro_id, version_id=version_id, uid_original="persona-ficticia-1", tipo_sujeto="PERSONA",
                                 contenido_original={"nombre": "Persona ficticia"}, huella_semantica="a" * 64))
        sesion.flush()
        version.manifiesto = {"solo_pruebas": True, "cantidad": 1, "huella": archivo.huella}
        version.cantidad_registros = 1
        version.estado = "VALIDA"
        sesion.add(EventoVersion(version_id=version_id, estado_anterior="EN_CONSTRUCCION", estado_nuevo="VALIDA",
                                actor_emisor=escenario.cargador.issuer, actor_sujeto=escenario.cargador.sub, motivo="Fixture completo"))
    return version_id, registro_id


def preparar_comparacion(escenario, destino, base=None, revision=0):
    identificador = uuid4()
    with escenario.sesiones.begin() as sesion:
        sesion.add(ComparacionVersion(id=identificador, fuente_id=escenario.fuente, base_id=base, destino_id=destino,
                                     revision_base=revision, version_comparador="fixture-v1", informe={"solo_pruebas": True}, huella="a" * 64))
    aprobacion = escenario.catalogo.revisar(escenario.aprobador, identificador, "APROBADA", "Comparación ficticia revisada")
    return identificador, aprobacion


def activar_version(escenario, comparacion, aprobacion, revision=0, clave="activacion-1", tipo="ACTIVACION"):
    return escenario.catalogo.activar(escenario.aprobador, escenario.fuente, comparacion, aprobacion, revision,
                                     escenario.politica_id, clave, "Cambio de versión de prueba", tipo)
