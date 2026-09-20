from infrastructure.persistencia.models import (
    ClasificacionTributariaFormulario,
    DatosPersonaNaturalFormulario,
    Formulario,
)
from infrastructure.persistencia.repositorios._formulario_helpers import (
    _purgar_relaciones_no_aplicables,
)


def test_purga_clasificacion_tributaria_cuando_tipo_final_es_natural():
    formulario = Formulario(tipo_persona="juridica")
    clasificacion = ClasificacionTributariaFormulario(
        actividad_clasificacion="Industrial",
        superintendencia="INTENDENCIA",
    )
    formulario.clasificacion_tributaria = clasificacion

    relaciones_eliminadas = _purgar_relaciones_no_aplicables(
        formulario,
        {"tipo_persona": "natural"},
    )

    assert formulario.clasificacion_tributaria is None
    assert relaciones_eliminadas == [clasificacion]


def test_purga_datos_naturales_cuando_tipo_final_es_juridica():
    formulario = Formulario(tipo_persona="natural")
    datos_naturales = DatosPersonaNaturalFormulario(
        direccion_residencia="probando",
        ciudad_residencia="probando jeje",
    )
    formulario.datos_persona_natural = datos_naturales

    relaciones_eliminadas = _purgar_relaciones_no_aplicables(
        formulario,
        {"tipo_persona": "juridica"},
    )

    assert formulario.datos_persona_natural is None
    assert relaciones_eliminadas == [datos_naturales]
