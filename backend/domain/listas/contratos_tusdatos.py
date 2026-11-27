"""Contrato de resultado propio de Tusdatos (modalidad externa).

Tusdatos no compara datos ni clasifica coincidencias: informa, por cada fuente, si encontró
registros y el detalle que publica la fuente. Este contrato refleja eso y nada más. No lleva
los campos de la búsqueda propia sobre archivos de listas (versiones fijadas, hashes de
contenido, puntajes, motivos de comparación, alias débiles…), que siguen en `contratos.py`
y `contratos_busqueda.py` para las modalidades simulada y de archivos.

La petición no cambia: se admite con `CrearConsultaV2` (contrato 2.0). Lo que cambia es el
resultado guardado, que se reconoce por `version_contrato = "tusdatos-1"`.
"""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints

from domain.listas.contratos import (
    DTO, Codigo, Conclusion, ContextoExpediente, ContextoIndependiente, Criterio, ErrorConsulta, Estado, Evidencia,
    Implementacion, Texto,
)

VERSION_CONTRATO_TUSDATOS = "tusdatos-1"

# CON_REGISTRO: la fuente respondió y tiene al menos un registro del consultado.
# SIN_REGISTRO: la fuente respondió sin registros.
# NO_CONSULTADA: Tusdatos informó error, la fuente estaba caída o la consulta no llegó a hacerse.
# NO_INCLUIDA: la fuente no vino en el reporte (no está en el plan o Tusdatos solo la envía con registro).
EstadoFuente = Literal["CON_REGISTRO", "SIN_REGISTRO", "NO_CONSULTADA", "NO_INCLUIDA"]
TextoLibre = Annotated[str, StringConstraints(min_length=1, max_length=2000, pattern=r"\S")]


class RegistroTusdatos(DTO):
    """Un registro que la fuente informa sobre el consultado, con el detalle tal como lo publica Tusdatos."""
    id: UUID
    campo: Codigo                      # campo del reporte de donde salió (p. ej. `contraloria2`, `peps_denom`)
    titulo: Texto                      # nombre del registro o resumen legible
    identificador_origen: Codigo | None = None
    categoria: Codigo | None = None    # en PEP: listas_restrictivas, listas_vinculantes, peps_internacionales
    sin_detalle: bool = False          # Tusdatos solo marcó que hay registro (`true`), sin datos
    detalle: dict = Field(default_factory=dict)  # estructura original, sin aplanar ni recortar
    detalle_recortado: bool = False    # True si el detalle superó el tamaño máximo y se guardó parcial


class HallazgoInformado(DTO):
    """Código de hallazgo que Tusdatos asoció a la fuente (`dict_hallazgos`). Su nivel lo configura la cuenta."""
    codigo: Codigo
    descripcion: TextoLibre
    nivel: Codigo | None = None


class FuenteTusdatos(DTO):
    id: UUID
    codigo: Codigo
    nombre: Texto
    estado: EstadoFuente
    requerida: bool = True
    motivo: TextoLibre | None = None
    # False: Tusdatos no publica el modelo de esta fuente; el detalle se muestra tal como llega.
    estructura_documentada: bool = True
    version_base: Codigo | None = None           # p. ej. `peps_version`
    resumen: tuple[dict, ...] = ()               # p. ej. `peps_consolidado`
    hallazgos: tuple[HallazgoInformado, ...] = ()
    registros: tuple[RegistroTusdatos, ...] = ()


class AvisoTusdatos(DTO):
    """Aviso general de la consulta. El estado de cada fuente no se repite aquí."""
    codigo: Codigo
    descripcion: TextoLibre


class ResultadoTusdatos(DTO):
    version_contrato: Literal["tusdatos-1"] = VERSION_CONTRATO_TUSDATOS
    consulta_id: UUID
    implementacion: Literal[Implementacion.EXTERNO] = Implementacion.EXTERNO
    proveedor: Codigo
    estado_ejecucion: Estado
    conclusion_busqueda: Conclusion | None
    titular_nombre: Texto | None = None          # nombre que Tusdatos resolvió para el documento
    documento_validado: bool | None = None
    nivel_informado_proveedor: Codigo | None = None
    fuentes: tuple[FuenteTusdatos, ...] = ()
    avisos: tuple[AvisoTusdatos, ...] = ()
    fecha_inicio: AwareDatetime
    fecha_fin: AwareDatetime | None = None
    error: ErrorConsulta | None = None


class ConsultaTusdatos(ResultadoTusdatos):
    contexto: Annotated[ContextoExpediente | ContextoIndependiente, Field(discriminator="tipo")]
    criterio: Criterio
    grupo_id: UUID | None = None
    fase: Literal["ADMISION", "BUSQUEDA", "PREPARANDO_EVIDENCIA", "CERRANDO", "FINALIZADA"]
    evidencias: tuple[Evidencia, ...] = ()
