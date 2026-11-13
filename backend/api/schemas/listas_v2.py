"""Contratos HTTP de listas; los permisos y la identidad nunca llegan en el cuerpo."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from domain.listas.contratos import Criterio, ConsultaV2
from domain.listas.contratos_busqueda import CriterioBusqueda, ConsultaBusquedaF6


class SolicitudConsultaLista(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"] = "CONTRAPARTE"
    criterio: Criterio
    motivo: str | None = Field(default=None, min_length=10, max_length=500)


class RevisionLista(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resultado: Literal["DESCARTADA", "IDENTIDAD_CORROBORADA", "REQUIERE_INFORMACION"]
    justificacion: str = Field(min_length=1, max_length=2000)
    coincidencia_id: UUID | None = None
    revision_previa_id: UUID | None = None


class SolicitudConsultaArchivos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_contrato: Literal["2.1"]
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"] = "CONTRAPARTE"
    criterio: CriterioBusqueda
    motivo: str | None = Field(default=None, min_length=10, max_length=500)


class AdmisionLista(BaseModel):
    consulta_id: UUID
    ubicacion: str


class DetalleConsultaLista(BaseModel):
    consulta: ConsultaV2 | ConsultaBusquedaF6 = Field(discriminator="version_contrato")
    revisiones: list[dict]


class ConsultaDelGrupo(BaseModel):
    consulta_id: UUID
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"]


class SujetoNoConsultado(BaseModel):
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"]
    motivo: str


class AdmisionGrupo(BaseModel):
    grupo_id: UUID
    consultas: list[ConsultaDelGrupo]
    no_consultados: list[SujetoNoConsultado]


class DisponibilidadListas(BaseModel):
    consultar: bool
    historial: bool
    revisar: bool
    implementacion: Literal["deshabilitado", "simulado", "archivos", "externo"]


class RevisionRegistrada(BaseModel):
    revision_id: UUID


class ResumenConsultaLista(BaseModel):
    consulta_id: UUID
    estado: Literal["PENDIENTE", "EN_CURSO", "COMPLETADA", "PARCIAL", "FALLIDA", "INDETERMINADA"]
    conclusion: Literal["SIN_CANDIDATOS", "CON_CANDIDATOS", "NO_CONCLUYENTE"] | None
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"]
    creado_en: str


class AntecedenteLista(BaseModel):
    campo: str | None
    resultado_original: str | None
    detalle: str | None


class LegadoListas(BaseModel):
    validaciones: list[AntecedenteLista]
    reporte_id: str | None
    evidencia_disponible: Literal[False]
    descripcion: str


class HistorialListas(BaseModel):
    consultas: list[ResumenConsultaLista]
    siguiente: UUID | None
    legado: LegadoListas
