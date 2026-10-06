"""API/repository contract for NOT NULL; SQLite in memory, no Alembic or AWS."""
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from api.schemas.acceso_manual import ActualizarCorreoAcceso, SolicitudAccesoManual
from domain.contratos import SolicitudCreacionAcceso
from domain.formulario.tipos import AreaResponsable
from infrastructure.persistencia.models import Base
from infrastructure.persistencia.repositorios.acceso_manual import RepositorioAccesoManualSQLAlchemy


def solicitud(correo):
    return SolicitudCreacionAcceso(tipo_contraparte='proveedor', razon_social='Prueba',
        area_responsable=next(iter(AreaResponsable)).value, correo_destinatario=correo)


@pytest.mark.parametrize('schema', [SolicitudAccesoManual, ActualizarCorreoAcceso])
@pytest.mark.parametrize('case', ['missing', 'null', 'empty', 'invalid'])
def test_api_rechaza_correo_invalido(schema, case):
    payload = dict(tipo_contraparte='proveedor', razon_social='Prueba',
                   area_responsable=next(iter(AreaResponsable)).value)
    if case != 'missing':
        payload['correo_destinatario'] = {'null': None, 'empty': '', 'invalid': 'incorrecto'}[case]
    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize('operation', ['crear', 'actualizar'])
@pytest.mark.parametrize('email', [None, '', '  '])
def test_repositorio_rechaza_correo_antes_de_cualquier_sql(operation, email):
    session = Mock()
    repo = RepositorioAccesoManualSQLAlchemy(session)
    with pytest.raises(ValueError, match='correo_destinatario'):
        if operation == 'crear':
            repo.crear_formulario_y_acceso(solicitud(email), 'hash', 'token')
        else:
            repo.actualizar_correo_por_token('token', email)
    assert session.mock_calls == []


def test_crear_y_actualizar_persisten_correo_con_not_null():
    engine = create_engine('sqlite:///:memory:')
    # ORM eager relationships require their tables too; no Alembic migrations.
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            result = RepositorioAccesoManualSQLAlchemy(session).crear_formulario_y_acceso(
                solicitud('inicial@example.org'), 'hash', 'token')
            assert result.correo_destinatario == 'inicial@example.org'
        with Session(engine) as session:
            repo = RepositorioAccesoManualSQLAlchemy(session)
            assert session.execute(text('SELECT correo_destinatario FROM accesos_manuales')).scalar_one() == 'inicial@example.org'
            repo.actualizar_correo_por_token('token', 'nuevo@example.org')
        with Session(engine) as session:
            assert session.execute(text('SELECT correo_destinatario FROM accesos_manuales')).scalar_one() == 'nuevo@example.org'
            with pytest.raises(ValueError):
                RepositorioAccesoManualSQLAlchemy(session).actualizar_correo_por_token('token', None)
            session.expire_all()
            assert session.execute(text('SELECT correo_destinatario FROM accesos_manuales')).scalar_one() == 'nuevo@example.org'
    finally:
        engine.dispose()
