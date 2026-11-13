"""Contrato 2.1 de F6; no reemplaza rutas ni contratos 2.0 de F3."""
import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from .contratos import (
    Codigo, ContextoExpediente, ConsultaV2, CrearConsultaV2, Criterio, DTO,
    Identificador, Pais, ResultadoProveedorV2, SolicitudIdempotente,
)
from .datos_busqueda import (
    CalidadDato, HechoComparacion, Huella, NivelCoincidencia, ReferenciaDato,
    TextoDato, UbicacionContexto, ValorIdentificador, NombreFuente, IdentificadorFuente, RelacionFuente,
)


class IdentificadorConsulta(Identificador):
    valor: ValorIdentificador
    esquema: Codigo | None = None
    digito_verificacion: Annotated[str, StringConstraints(pattern=r"^[0-9]$")] | None = None


class CriterioBusqueda(Criterio):
    tipo_sujeto: Literal["PERSONA", "ENTIDAD", "NO_DETERMINADO"]
    nombre: TextoDato | None = None
    nombres_adicionales: tuple[TextoDato, ...] = Field(default=(), max_length=10)
    identificadores: tuple[IdentificadorConsulta, ...] = Field(default=(), max_length=10)
    ciudadanias: tuple[Pais, ...] = Field(default=(), max_length=10)
    ubicaciones: tuple[UbicacionContexto, ...] = Field(default=(), max_length=20)
    campos_exigidos: tuple[Codigo, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def no_exigir_datos_ausentes(self):
        campos = {
            "nombre": bool(self.nombre), "nombres_adicionales": bool(self.nombres_adicionales),
            "identificadores": bool(self.identificadores),
            "fecha_nacimiento": self.fecha_nacimiento is not None,
            "fecha_expedicion": self.fecha_expedicion is not None,
            "nacionalidades": bool(self.nacionalidades), "ciudadanias": bool(self.ciudadanias),
            "ubicacion": self.ubicacion is not None, "ubicaciones": bool(self.ubicaciones),
        }
        if len(set(self.campos_exigidos)) != len(self.campos_exigidos):
            raise ValueError("Criterios exigidos duplicados")
        if any(not campos.get(campo, False) for campo in self.campos_exigidos):
            raise ValueError("No se puede exigir un criterio inexistente o no informado")
        return self


class CrearConsultaBusqueda(CrearConsultaV2):
    version_contrato: Literal["2.1"] = "2.1"
    contexto: ContextoExpediente
    criterio: CriterioBusqueda


class SolicitudIdempotenteBusqueda(SolicitudIdempotente):
    solicitud: CrearConsultaBusqueda


class MotivoClasificacion(DTO):
    campo: Codigo
    resultado: Literal["COINCIDE", "COMPATIBLE", "DIFERENTE", "AUSENTE", "NO_APLICADO"]
    metodo: Codigo
    explicacion: TextoDato
    valor_consultado: TextoDato | None = None
    valor_fuente: TextoDato | None = None
    calidad_fuente: CalidadDato = CalidadDato.DESCONOCIDO
    referencia: ReferenciaDato | None = None

    @model_validator(mode="after")
    def exigir_valores_comparados(self):
        if self.resultado in {"COINCIDE", "COMPATIBLE", "DIFERENTE"}:
            if self.valor_consultado is None or self.valor_fuente is None or self.referencia is None:
                raise ValueError("Una comparación necesita ambos valores y referencia de origen")
        if self.resultado == "AUSENTE" and self.valor_consultado is not None and self.valor_fuente is not None:
            raise ValueError("Ausencia no puede representar dos valores presentes")
        return self


class CandidatoClasificado(DTO):
    id: UUID
    cobertura_id: UUID
    registro_id: UUID | None = None
    uid_origen: ValorIdentificador | None = None
    tipo_sujeto: Literal["PERSONA", "ENTIDAD", "NO_DETERMINADO"]
    nombre_principal: TextoDato
    nivel: NivelCoincidencia
    regla_codigo: Codigo
    regla_version: Codigo
    explicacion: TextoDato
    motivos: tuple[MotivoClasificacion, ...] = Field(min_length=1)
    revision_prioritaria: bool = False
    hechos: tuple[HechoComparacion, ...] = ()
    nombres: tuple[NombreFuente, ...] = ()
    identificadores: tuple[IdentificadorFuente, ...] = ()
    relaciones: tuple[RelacionFuente, ...] = ()
    algoritmo_version: Codigo

    @model_validator(mode="after")
    def no_admitir_motivos_sin_coincidencia(self):
        if not any(m.resultado in {"COINCIDE", "COMPATIBLE"} for m in self.motivos):
            raise ValueError("Un candidato necesita algún motivo positivo de recuperación")
        return self


class ResultadoBusquedaF6(ResultadoProveedorV2):
    version_contrato: Literal["2.1"] = "2.1"
    candidatos: tuple[CandidatoClasificado, ...] = ()
    generador_informe_version: Literal["informe-listas-v1", "informe-listas-f6-v2"] = "informe-listas-v1"

    @model_validator(mode="after")
    def verificar_procedencia(self):
        _comprobar_procedencia(self)
        return self


def _comprobar_procedencia(resultado):
    if resultado.implementacion != "archivos":
        return
    coberturas = {c.id: c for c in resultado.cobertura}
    for candidato in resultado.candidatos:
        cobertura = coberturas[candidato.cobertura_id]
        if cobertura.estado != "CONSULTADA" or not cobertura.version_id:
            raise ValueError("Un candidato local necesita cobertura efectivamente consultada")
        referencias = [m.referencia for m in candidato.motivos if m.referencia]
        referencias += [h.referencia for h in candidato.hechos]
        referencias += [d.referencia for d in (*candidato.nombres, *candidato.identificadores, *candidato.relaciones)]
        for ref in referencias:
            if (ref.fuente_codigo, ref.version_id, ref.registro_id) != (
                    cobertura.fuente_codigo, cobertura.version_id, candidato.registro_id):
                raise ValueError("Motivo o hecho pertenece a otro registro, fuente o versión")


class VersionBusquedaFijada(DTO):
    fuente_codigo: Codigo
    version_id: UUID
    revision_activa: int = Field(ge=0, strict=True)
    hash_contenido: Huella
    generacion_id: UUID
    generacion_hash: Huella
    version_adaptador: Codigo
    version_normalizacion: Codigo

    # La disponibilidad/activación real se comprobará con persistencia en F6.2.


class ManifiestoBusqueda(DTO):
    version_contrato: Literal["2.1"] = "2.1"
    politica_version: Codigo
    reglas_version: Codigo
    algoritmo_version: Codigo
    catalogos_hash: Huella
    parametros_internos_hash: Huella
    fuentes: tuple[VersionBusquedaFijada, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def una_version_por_fuente(self):
        codigos = [fuente.fuente_codigo for fuente in self.fuentes]
        if len(codigos) != len(set(codigos)):
            raise ValueError("Una consulta no puede mezclar versiones de una misma fuente")
        return self

    @property
    def huella(self):
        datos = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(datos.encode()).hexdigest()


class ConsultaBusquedaF6(ConsultaV2):
    version_contrato: Literal["2.1"] = "2.1"
    contexto: ContextoExpediente
    criterio: CriterioBusqueda
    candidatos: tuple[CandidatoClasificado, ...] = ()
    generador_informe_version: Literal["informe-listas-v1", "informe-listas-f6-v2"] = "informe-listas-v1"
    trazabilidad: ManifiestoBusqueda | None = None

    @model_validator(mode="after")
    def verificar_procedencia(self):
        _comprobar_procedencia(self)
        return self


class SolicitudBusquedaInterna(DTO):
    """La construye admisión, nunca el cuerpo HTTP ni un adaptador."""
    consulta_id: UUID
    correlacion_id: UUID
    contexto: ContextoExpediente
    criterio: CriterioBusqueda
    proveedor: Codigo
    implementacion: Literal["archivos", "externo"]
    admitida_en: AwareDatetime
    manifiesto: ManifiestoBusqueda


class CapacidadesBusqueda(DTO):
    proveedor: Codigo
    adaptador_version: Codigo
    campos: tuple[Codigo, ...] = Field(min_length=1)
    esquemas_identificador: tuple[Codigo, ...] = ()
    tipos_sujeto: tuple[Literal["PERSONA", "ENTIDAD", "NO_DETERMINADO"], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def no_duplicar_capacidades(self):
        if any(len(valores) != len(set(valores)) for valores in (
                self.campos, self.esquemas_identificador, self.tipos_sujeto)):
            raise ValueError("Capacidades duplicadas")
        return self
