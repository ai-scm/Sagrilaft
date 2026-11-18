"""La optimización del cierre conserva los controles SQL, sin llamar al verificador Python."""
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda
from .test_busqueda_f62 import busqueda
from .test_administracion_f55 import administracion
from .test_recepcion_f52 import carga
from .test_flujo_http import portal


@pytest.mark.parametrize("alteracion", ["sin_nombre", "sin_identificador", "termino_adicional"])
def test_f66_sql_rechaza_terminos_incompletos_o_adicionales(busqueda, alteracion):
    a = busqueda
    original = a.busqueda.preparar(a.actor, a.version)
    nueva = uuid4()
    with pytest.raises(DBAPIError, match="Índice de búsqueda incompleto"), a.sesiones.begin() as sesion:
        anterior = sesion.get(GeneracionBusqueda, original)
        generacion = GeneracionBusqueda(id=nueva, version_id=a.version,
            adaptador_version="ensayo-"+alteracion, normalizacion_version=anterior.normalizacion_version,
            catalogo_huella=anterior.catalogo_huella, cantidad_registros=anterior.cantidad_registros,
            cantidad_consultables=anterior.cantidad_consultables, huella=anterior.huella)
        sesion.add(generacion)
        sesion.flush()
        sesion.execute(text("""INSERT INTO registro_busqueda_lista
            SELECT :nueva, registro_id, version_id, datos, motivo_exclusion, huella
            FROM registro_busqueda_lista WHERE generacion_id=:original"""),dict(nueva=nueva,original=original))
        filtro = {"sin_nombre":"AND clase<>'NOMBRE'", "sin_identificador":"AND clase<>'IDENTIFICADOR'",
                  "termino_adicional":""}[alteracion]
        sesion.execute(text("""INSERT INTO termino_busqueda_lista
            SELECT :nueva, registro_id, clase, ordinal, huella_valor
            FROM termino_busqueda_lista WHERE generacion_id=:original """+filtro),dict(nueva=nueva,original=original))
        if alteracion == "termino_adicional":
            sesion.execute(text("""INSERT INTO termino_busqueda_lista
                SELECT :nueva, registro_id, clase, ordinal+100, huella_valor
                FROM termino_busqueda_lista WHERE generacion_id=:original LIMIT 1"""),dict(nueva=nueva,original=original))
        generacion.estado = "LISTA"
        sesion.flush()
    with a.sesiones() as sesion:
        assert sesion.get(GeneracionBusqueda,nueva) is None
        assert sesion.get(GeneracionBusqueda,original).estado == "LISTA"


def test_f66_migracion_agrupada_revierte_y_reaplica_sin_cambiar_datos(busqueda, administracion_bd):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    a = busqueda
    identificador = a.busqueda.preparar(a.actor,a.version)
    with a.sesiones() as sesion:
        huella = sesion.get(GeneracionBusqueda,identificador).huella
    configuracion = Config(str(Path(__file__).parents[2]/"backend/alembic.ini"))
    command.downgrade(configuracion,"i09d12e345f6")
    with administracion_bd.connect() as conexion:
        anterior = conexion.scalar(text("SELECT pg_get_functiondef('listas_comprobar_generacion()'::regprocedure)"))
        assert "coalesce(t.nombres" not in anterior
    command.upgrade(configuracion,"head")
    # Reaplicar recrea las tablas posteriores (p. ej. progreso_consulta_externa): se restauran
    # los permisos del fixture, como en las demás pruebas que revierten, solo en /tmp.
    with administracion_bd.begin() as conexion:
        conexion.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aplicacion_listas"))
    with administracion_bd.connect() as conexion:
        actual = conexion.scalar(text("SELECT pg_get_functiondef('listas_comprobar_generacion()'::regprocedure)"))
        assert "coalesce(t.nombres" in actual
    with a.sesiones() as sesion:
        generacion = sesion.get(GeneracionBusqueda,identificador)
        assert generacion.huella == huella
        assert len(a.busqueda._verificar(sesion,generacion)) == generacion.cantidad_registros
