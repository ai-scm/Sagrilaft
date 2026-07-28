"""
Helpers específicos del formulario: contactos, relaciones dinámicas 1:N,
relaciones condicionales 1:1 y purga de datos por tipo de persona.
"""

from typing import Any, Dict, List, Optional

from domain.formulario.reglas_tipo_persona import (
    _CAMPOS_CLASIFICACION_TRIBUTARIA,
    _CAMPOS_PERSONA_NATURAL,
    purgar_campos_no_aplicables,
)
from domain.formulario.tipos import TipoPersona
from infrastructure.persistencia.models import (
    AccionistaFormulario,
    BeneficiarioFinalFormulario,
    ClasificacionTributariaFormulario,
    ContactoFormulario,
    CuentaPagoFormulario,
    DatosPersonaNaturalFormulario,
    Formulario,
    MiembroJuntaDirectiva,
    ReferenciaBancariaDeclarada,
    ReferenciaComercialFormulario,
    TipoTransaccionFormulario,
)

_CONTACTOS_FORMULARIO = {
    "ordenes": "contacto_ordenes",
    "pagos": "contacto_pagos",
}

_ATRIBUTOS_CONTACTO = ["nombre", "cargo", "telefono", "correo"]

# Listas dinámicas del formulario que hoy viven en tablas 1:N propias
# (Cambio 1 del rediseño de esquema). Cada entrada mapea el nombre de la
# relación en Formulario -> (clase ORM hija, atributos que expone al dominio).
# Los atributos son exactamente el shape que ya esperaban dominio/API/PDF/
# validación cuando estos campos eran JSON — la costura no cambia su forma.
_TABLAS_LISTA_FORMULARIO = {
    "junta_directiva": (MiembroJuntaDirectiva, [
        "cargo", "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep",
    ]),
    "accionistas": (AccionistaFormulario, [
        "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep", "porcentaje",
    ]),
    "beneficiario_final": (BeneficiarioFinalFormulario, [
        "nombre", "tipo_id", "numero_id", "es_pep", "vinculos_pep", "porcentaje",
    ]),
    "referencias_comerciales": (ReferenciaComercialFormulario, [
        "nombre_establecimiento", "persona_contacto", "telefono", "ciudad",
    ]),
    "referencias_bancarias": (ReferenciaBancariaDeclarada, ["entidad", "producto"]),
    "informacion_bancaria_pagos": (CuentaPagoFormulario, [
        "entidad_bancaria", "ciudad_oficina", "tipo_cuenta", "numero_cuenta",
    ]),
}


def _construir_filas_hijas(modelo_cls: type, atributos: List[str], valor: Any) -> List[Any]:
    """Convierte una lista de dicts (payload del cliente) en instancias ORM hijas, preservando orden."""
    filas = valor or []
    return [
        modelo_cls(orden=indice, **{atributo: fila.get(atributo) for atributo in atributos})
        for indice, fila in enumerate(filas)
    ]


def _construir_relaciones_dinamicas(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reemplaza, para las claves presentes en `datos`, las listas de dicts de las
    tablas dinámicas del formulario por listas de instancias ORM hijas listas
    para asignar a la relación (SQLAlchemy reemplaza la colección completa,
    incluyendo el borrado de las filas huérfanas gracias a delete-orphan).
    """
    resultado = dict(datos)
    for campo, (modelo_cls, atributos) in _TABLAS_LISTA_FORMULARIO.items():
        if campo in resultado:
            resultado[campo] = _construir_filas_hijas(modelo_cls, atributos, resultado[campo])
    if "tipos_transaccion" in resultado:
        resultado["tipos_transaccion"] = [
            TipoTransaccionFormulario(tipo=tipo) for tipo in (resultado["tipos_transaccion"] or [])
        ]
    return resultado


def _extraer_campos_contacto(datos: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Agrupa los campos planos contacto_* por tipo interno de contacto."""
    contactos: Dict[str, Dict[str, Any]] = {}
    for tipo, prefijo in _CONTACTOS_FORMULARIO.items():
        valores = {
            atributo: datos[f"{prefijo}_{atributo}"]
            for atributo in _ATRIBUTOS_CONTACTO
            if f"{prefijo}_{atributo}" in datos
        }
        if valores:
            contactos[tipo] = valores
    return contactos


def _extraer_contactos_para_creacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte campos planos de contacto en filas hijas y los remueve del payload del ORM padre."""
    resultado = dict(datos)
    contactos = _extraer_campos_contacto(resultado)
    for prefijo in _CONTACTOS_FORMULARIO.values():
        for atributo in _ATRIBUTOS_CONTACTO:
            resultado.pop(f"{prefijo}_{atributo}", None)
    if contactos:
        resultado["contactos"] = [
            ContactoFormulario(tipo=tipo, **valores)
            for tipo, valores in contactos.items()
        ]
    return resultado


def _extraer_relaciones_uno_a_uno_para_creacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte campos planos condicionales en sus tablas 1:1 de lenguaje de negocio."""
    resultado = dict(datos)

    datos_natural = {
        campo: resultado.pop(campo)
        for campo in _CAMPOS_PERSONA_NATURAL
        if campo in resultado
    }
    if datos_natural:
        resultado["datos_persona_natural"] = DatosPersonaNaturalFormulario(**datos_natural)

    clasificacion = {
        campo: resultado.pop(campo)
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA
        if campo in resultado
    }
    if clasificacion:
        resultado["clasificacion_tributaria"] = ClasificacionTributariaFormulario(**clasificacion)

    return resultado


def _aplicar_actualizacion_relaciones_uno_a_uno(orm: Formulario, campos: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica campos condicionales 1:1 y devuelve solo los campos que pertenecen a formularios."""
    restantes = dict(campos)

    datos_natural = {
        campo: restantes.pop(campo)
        for campo in _CAMPOS_PERSONA_NATURAL
        if campo in restantes
    }
    if datos_natural:
        if orm.datos_persona_natural is None:
            orm.datos_persona_natural = DatosPersonaNaturalFormulario()
        for campo, valor in datos_natural.items():
            setattr(orm.datos_persona_natural, campo, valor)

    clasificacion = {
        campo: restantes.pop(campo)
        for campo in _CAMPOS_CLASIFICACION_TRIBUTARIA
        if campo in restantes
    }
    if clasificacion:
        if orm.clasificacion_tributaria is None:
            orm.clasificacion_tributaria = ClasificacionTributariaFormulario()
        for campo, valor in clasificacion.items():
            setattr(orm.clasificacion_tributaria, campo, valor)

    return restantes


def _tipo_persona_efectivo(orm: Optional[Formulario], datos: Dict[str, Any]) -> str:
    return str(datos.get("tipo_persona") or getattr(orm, "tipo_persona", "") or "").lower()


def _purgar_datos_no_aplicables_en_payload(datos: Dict[str, Any], orm: Optional[Formulario] = None) -> Dict[str, Any]:
    """
    Quita del payload los bloques que no corresponden al tipo de persona.
    Esta defensa vive en backend para que la integridad no dependa solo del UI.
    """
    tipo_persona = _tipo_persona_efectivo(orm, datos)
    return purgar_campos_no_aplicables(datos, tipo_persona)


def _purgar_relaciones_no_aplicables(orm: Formulario, datos: Dict[str, Any]) -> List[Any]:
    tipo_persona = _tipo_persona_efectivo(orm, datos)
    relaciones_eliminadas: List[Any] = []
    if tipo_persona == TipoPersona.NATURAL.value:
        if orm.clasificacion_tributaria is not None:
            relaciones_eliminadas.append(orm.clasificacion_tributaria)
        orm.clasificacion_tributaria = None
        orm.junta_directiva = []
        orm.accionistas = []
        orm.beneficiario_final = []
    elif tipo_persona == TipoPersona.JURIDICA.value:
        if orm.datos_persona_natural is not None:
            relaciones_eliminadas.append(orm.datos_persona_natural)
        orm.datos_persona_natural = None
    return relaciones_eliminadas


def _aplicar_actualizacion_contactos(orm: Formulario, campos: Dict[str, Any]) -> None:
    """Aplica cambios parciales de los 8 campos planos a la relación contactos."""
    contactos = _extraer_campos_contacto(campos)
    if not contactos:
        return

    existentes = {contacto.tipo: contacto for contacto in orm.contactos}
    for tipo, valores in contactos.items():
        contacto = existentes.get(tipo)
        if contacto is None:
            contacto = ContactoFormulario(tipo=tipo)
            orm.contactos.append(contacto)
        for atributo, valor in valores.items():
            setattr(contacto, atributo, valor)


def _contacto_por_tipo(orm: Formulario, tipo: str) -> Optional[ContactoFormulario]:
    for contacto in orm.contactos:
        if contacto.tipo == tipo:
            return contacto
    return None


def _valor_contacto(orm: Formulario, tipo: str, atributo: str) -> Optional[str]:
    contacto = _contacto_por_tipo(orm, tipo)
    return getattr(contacto, atributo) if contacto else None
