import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("APP_ENV", "development")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.formulario.tipos import EstadoFormulario
from domain.formulario.entidades import FormularioDatos
from infrastructure.persistencia.database import Base
from infrastructure.persistencia.models import Formulario, ClasificacionTributariaFormulario
from infrastructure.persistencia.repositorios.formulario import RepositorioFormularioSQLAlchemy

@pytest.fixture
def session():
    """Crea una base de datos en memoria y retorna una sesión de SQLAlchemy."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_autoguardado_preserva_booleanos_nulos(session):
    """
    Verifica que al guardar un borrador con campos booleanos vacíos (None/null),
    el repositorio los preserve como NULL en lugar de coaccionarlos a False.
    """
    repo = RepositorioFormularioSQLAlchemy(session)
    
    # 1. Crear borrador vacío (los campos booleanos no se envían)
    datos_creacion = {
        "tipo_persona": "juridica",
    }
    
    formulario_creado = repo.crear(datos_creacion)
    form_id = formulario_creado.id
    
    # 2. Afirmar que el valor es None inicialmente (después de crear)
    assert formulario_creado.autorretenedor is None
    assert formulario_creado.realiza_operaciones_moneda_extranjera is None
    
    # Comprobar directamente en BD
    form_bd = session.query(Formulario).filter_by(id=form_id).first()
    assert form_bd.realiza_operaciones_moneda_extranjera is None
    assert form_bd.clasificacion_tributaria is None  # no se creó todavía porque no enviamos campos
    
    # 3. Actualizar el borrador asignando explícitamente otros campos de clasificación,
    # pero enviando None explícito (como hace sanitizarPayload del frontend) para un booleano.
    datos_actualizacion = {
        "actividad_clasificacion": "Industrial",
        "autorretenedor": None,
        "gran_contribuyente": False,
        "entidad_sin_animo_lucro": True
    }
    
    formulario_actualizado = repo.actualizar(form_id, datos_actualizacion)
    
    # 4. Afirmar que los valores se conservan según lo enviado
    assert formulario_actualizado.autorretenedor is None
    assert formulario_actualizado.gran_contribuyente is False
    assert formulario_actualizado.entidad_sin_animo_lucro is True
    
    # Comprobar en BD la correcta serialización
    clasificacion_bd = session.query(ClasificacionTributariaFormulario).filter_by(formulario_id=form_id).first()
    assert clasificacion_bd is not None
    assert clasificacion_bd.autorretenedor is None
    assert clasificacion_bd.gran_contribuyente is False
    assert clasificacion_bd.entidad_sin_animo_lucro is True

def test_validador_envio_rechaza_nulos():
    """
    Verifica que el validador de envío rechace los booleanos en None para evitar 
    que el formulario se envíe sin completarlos, ya que ahora sí llegarán como None.
    """
    from services.formulario.validacion_envio import ValidadorEnvioFormulario
    validador = ValidadorEnvioFormulario()
    
    # Formulario Persona Jurídica con todos los campos llenos excepto un booleano
    # (Por brevedad solo pasamos lo que ValidadorEnvioFormulario evaluaría)
    datos = FormularioDatos(
        id="123",
        codigo_peticion="SAG-123",
        estado=EstadoFormulario.BORRADOR.value,
        tipo_persona="juridica",
        # Simulamos que todo está completo pero falta 'autorretenedor'
        autorretenedor=None, 
        gran_contribuyente=False
    )
    
    # Invocamos la validación específica para clasificación tributaria
    errores = validador._validar_clasificacion_tributaria(datos)
    
    # Afirmar que se encontró un error por falta de 'autorretenedor'
    error_autorretenedor = next((e for e in errores if e.campo == "autorretenedor"), None)
    assert error_autorretenedor is not None
    assert error_autorretenedor.mensaje == "El campo 'Autorretenedor' es obligatorio"
