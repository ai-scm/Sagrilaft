"""Persistencia común de proyecciones de fuentes; no interpreta archivos."""
from infrastructure.persistencia.modelos_listas import (RegistroLista, NombreRegistro,
    IdentificadorRegistro, DireccionRegistro, AtributoRegistro, RelacionRegistro)
from services.listas.informes import calcular_huella


TABLAS_PROYECCION = {'nombres':NombreRegistro, 'identificadores':IdentificadorRegistro,
                     'direcciones':DireccionRegistro, 'atributos':AtributoRegistro}


def guardar_registro(sesion, version_id, contenido, proyectar):
    registro = RegistroLista(version_id=version_id, uid_original=contenido['uid'], tipo_sujeto=contenido['clase'],
        contenido_original=contenido, huella_semantica=calcular_huella(contenido))
    sesion.add(registro); sesion.flush()
    datos = proyectar(contenido)
    for nombre, tabla in TABLAS_PROYECCION.items():
        for ordinal, valores in enumerate(datos[nombre]):
            sesion.add(tabla(registro_id=registro.id, ordinal=ordinal, **valores))
    for valores in datos['relaciones']:
        sesion.add(RelacionRegistro(version_id=version_id, registro_origen_id=registro.id, **valores))
    return registro
