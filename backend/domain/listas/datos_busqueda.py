"""Hechos comunes de búsqueda F6. No interpreta XML ni calcula coincidencias."""
from calendar import monthrange
from datetime import date
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from .contratos import Codigo, DTO, Pais

TextoDato = Annotated[str, StringConstraints(min_length=1, max_length=4000, pattern=r"\S")]
ValorIdentificador = Annotated[str, StringConstraints(min_length=1, max_length=2048, pattern=r"\S")]
Huella = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class NivelCoincidencia(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class CalidadDato(str, Enum):
    CONFIRMADO = "CONFIRMADO"
    REPORTADO = "REPORTADO"
    DESCONOCIDO = "DESCONOCIDO"
    FALSO = "FALSO"


class ReferenciaDato(DTO):
    fuente_codigo: Codigo
    version_id: UUID | None = None
    registro_id: UUID | None = None
    respuesta_sha256: Huella | None = None
    campo_original: TextoDato
    identidad_origen: Codigo | None = None

    @model_validator(mode="after")
    def exigir_origen_reproducible(self):
        if (self.version_id is None) != (self.registro_id is None):
            raise ValueError("Versión y registro de origen deben declararse juntos")
        if self.version_id is None and self.respuesta_sha256 is None:
            raise ValueError("El dato requiere versión/registro o hash de respuesta custodiada")
        return self


class PartesFecha(DTO):
    anio: int = Field(ge=1, le=9999, strict=True)
    mes: int | None = Field(default=None, ge=1, le=12, strict=True)
    dia: int | None = Field(default=None, ge=1, le=31, strict=True)

    @model_validator(mode="after")
    def validar_componentes(self):
        if self.dia is not None:
            if self.mes is None or self.dia > monthrange(self.anio, self.mes)[1]:
                raise ValueError("Día incompatible con el año y mes declarados")
        return self


class FechaDato(DTO):
    original: TextoDato
    calendario: Codigo
    precision: Literal["DIA", "MES", "ANIO", "RANGO", "NO_INTERPRETADA"]
    valor: PartesFecha | None = None
    desde: PartesFecha | None = None
    hasta: PartesFecha | None = None
    aproximada: bool = False

    @model_validator(mode="after")
    def validar_precision(self):
        if self.calendario != "GREGORIANO" and self.precision != "NO_INTERPRETADA":
            raise ValueError("Un calendario no interpretado no admite componentes gregorianos")
        if self.precision == "NO_INTERPRETADA":
            if any((self.valor, self.desde, self.hasta)):
                raise ValueError("Una fecha no interpretada no puede inventar componentes")
        elif self.precision == "RANGO":
            if self.valor or not self.desde or not self.hasta:
                raise ValueError("El rango necesita dos límites y no un valor único")
            inicio = (self.desde.anio, self.desde.mes or 1, self.desde.dia or 1)
            fin = (self.hasta.anio, self.hasta.mes or 12,
                   self.hasta.dia or monthrange(self.hasta.anio, self.hasta.mes or 12)[1])
            # Solo verificar orden posible; estos límites no se guardan como fechas inferidas.
            if inicio > fin:
                raise ValueError("Rango de fechas invertido")
        else:
            if not self.valor or self.desde or self.hasta:
                raise ValueError("La fecha necesita un valor y no límites de rango")
            esperada = "DIA" if self.valor.dia else "MES" if self.valor.mes else "ANIO"
            if self.precision != esperada:
                raise ValueError("Precisión incompatible con los componentes conservados")
        return self


class ParteNombre(DTO):
    tipo: Codigo
    valor: TextoDato


class NombreFuente(DTO):
    valor: TextoDato
    tipo: Literal["PRINCIPAL", "ALIAS", "ANTERIOR"]
    alias_debil: bool = False
    alfabeto: Codigo | None = None
    partes: tuple[ParteNombre, ...] = Field(default=(), max_length=100)
    calidad: CalidadDato = CalidadDato.DESCONOCIDO
    referencia: ReferenciaDato


class VigenciaIdentificador(DTO):
    desde: date
    hasta: date
    calidad: CalidadDato = CalidadDato.DESCONOCIDO

    @model_validator(mode="after")
    def ordenar_periodo(self):
        if self.desde > self.hasta:
            raise ValueError("Vigencia del identificador invertida")
        return self


class IdentificadorFuente(DTO):
    tipo: Codigo
    esquema: Codigo | None = None
    valor: ValorIdentificador
    pais_emisor: Pais | None = None
    digito_verificacion: Annotated[str, StringConstraints(pattern=r"^[0-9]$")] | None = None
    calidad: CalidadDato = CalidadDato.DESCONOCIDO
    vigencia: VigenciaIdentificador | None = None
    referencia: ReferenciaDato


class UbicacionContexto(DTO):
    rol: Literal["DOMICILIO", "RESIDENCIA", "NACIMIENTO", "EMISION", "REGISTRO", "FUNCIONES", "OTRO"]
    texto: TextoDato | None = None
    pais: Pais | None = None
    historica: bool = False

    @model_validator(mode="after")
    def exigir_ubicacion(self):
        if self.texto is None and self.pais is None:
            raise ValueError("La ubicación debe contener texto o país")
        return self


class HechoFuente(DTO):
    campo: Codigo
    calidad: CalidadDato = CalidadDato.DESCONOCIDO
    referencia: ReferenciaDato


class HechoTexto(HechoFuente):
    tipo: Literal["TEXTO"] = "TEXTO"
    valor: TextoDato


class HechoFecha(HechoFuente):
    tipo: Literal["FECHA"] = "FECHA"
    valor: FechaDato


class HechoUbicacion(HechoFuente):
    tipo: Literal["UBICACION"] = "UBICACION"
    valor: UbicacionContexto


HechoComparacion = Annotated[HechoTexto | HechoFecha | HechoUbicacion, Field(discriminator="tipo")]


class RelacionFuente(DTO):
    tipo: Codigo
    direccion: Literal["ENTRANTE", "SALIENTE"]
    fuente_destino: Codigo
    version_destino_id: UUID
    registro_destino_id: UUID
    referencia: ReferenciaDato


class RegistroBusqueda(DTO):
    tipo_sujeto: Literal["PERSONA", "ENTIDAD", "NO_DETERMINADO"]
    referencia: ReferenciaDato
    nombres: tuple[NombreFuente, ...] = Field(min_length=1)
    identificadores: tuple[IdentificadorFuente, ...] = ()
    hechos: tuple[HechoComparacion, ...] = ()
    relaciones: tuple[RelacionFuente, ...] = ()

    @model_validator(mode="after")
    def conservar_pertenencia(self):
        esperada = (self.referencia.fuente_codigo, self.referencia.version_id,
                    self.referencia.registro_id, self.referencia.respuesta_sha256)
        for dato in (*self.nombres, *self.identificadores, *self.hechos, *self.relaciones):
            ref = dato.referencia
            if (ref.fuente_codigo, ref.version_id, ref.registro_id, ref.respuesta_sha256) != esperada:
                raise ValueError("Un hecho no puede pertenecer a otro registro o versión")
        return self
