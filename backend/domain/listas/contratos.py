"""Especificación ejecutable v2. Los resultados del adaptador aún no son evidencia final."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Texto = Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"\S")]
Codigo = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"\S")]
Pais = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
ClaveIdempotencia = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"\S")]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Implementacion(str, Enum):
    DESHABILITADO = "deshabilitado"
    SIMULADO = "simulado"
    ARCHIVOS = "archivos"
    EXTERNO = "externo"


class Estado(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_CURSO = "EN_CURSO"
    COMPLETADA = "COMPLETADA"
    PARCIAL = "PARCIAL"
    FALLIDA = "FALLIDA"
    INDETERMINADA = "INDETERMINADA"


class Conclusion(str, Enum):
    SIN_CANDIDATOS = "SIN_CANDIDATOS"
    CON_CANDIDATOS = "CON_CANDIDATOS"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


class Identificador(DTO):
    tipo: Codigo
    valor: Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"\S")]
    pais_emisor: Pais | None = None


class Ubicacion(DTO):
    pais: Pais | None = None
    texto: Texto | None = None


class Criterio(DTO):
    tipo_sujeto: Literal["PERSONA", "ENTIDAD", "BUQUE", "AERONAVE", "NO_DETERMINADO"]
    nombre: Texto | None = None
    nombres_adicionales: tuple[Texto, ...] = Field(default=(), max_length=10)
    identificadores: tuple[Identificador, ...] = Field(default=(), max_length=10)
    fecha_nacimiento: date | None = None
    fecha_expedicion: date | None = None
    nacionalidades: tuple[Pais, ...] = Field(default=(), max_length=10)
    ubicacion: Ubicacion | None = None

    @model_validator(mode="after")
    def criterio_primario(self):
        if not (self.nombre or self.nombres_adicionales or self.identificadores):
            raise ValueError("Se requiere un nombre o identificador utilizable")
        return self


class ContextoExpediente(DTO):
    tipo: Literal["EXPEDIENTE"]
    expediente_id: Codigo
    sujeto_rol: Literal["CONTRAPARTE", "REPRESENTANTE"]
    motivo: Annotated[str, StringConstraints(min_length=10, max_length=500, pattern=r"\S")] | None = None


class ContextoIndependiente(DTO):
    tipo: Literal["INDEPENDIENTE"]
    motivo: Annotated[str, StringConstraints(min_length=10, max_length=500, pattern=r"\S")]


class CrearConsultaV2(DTO):
    version_contrato: Literal["2.0"]
    contexto: Annotated[ContextoExpediente | ContextoIndependiente, Field(discriminator="tipo")]
    criterio: Criterio


class SolicitudIdempotente(DTO):
    """El transporte aporta la cabecera; F2 reservará la clave transaccionalmente."""
    clave: ClaveIdempotencia
    solicitud: CrearConsultaV2

    @property
    def hash_cuerpo(self) -> str:
        cuerpo = json.dumps(self.solicitud.model_dump(mode="json"), sort_keys=True,
                            ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()


class Cobertura(DTO):
    id: UUID
    fuente_codigo: Codigo | None = None
    nombre_origen: Texto
    version_id: UUID | None = None
    version_declarada: Codigo | None = None
    publicada_en: date | None = None
    hash_contenido: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    revision_activa: int | None = Field(default=None, ge=0)
    estado: Literal["PENDIENTE", "CONSULTADA", "NO_DISPONIBLE", "FALLIDA", "DESCONOCIDA"]
    requerida: bool = True
    motivo: Texto | None = None


class Motivo(DTO):
    campo: Codigo
    valor_consultado: Texto
    valor_registro: Texto
    metodo: Literal["EXACTO_DOCUMENTO", "EXACTO_NOMBRE", "SIMILITUD_NOMBRE", "PROVEEDOR"]


class Candidato(DTO):
    id: UUID
    cobertura_id: UUID
    registro_id: UUID | None = None
    uid_origen: Codigo | None = None
    tipo_sujeto: Literal["PERSONA", "ENTIDAD", "BUQUE", "AERONAVE", "NO_DETERMINADO"]
    nombre_principal: Texto
    nombres: tuple[Texto, ...] = ()
    identificadores: tuple[Identificador, ...] = ()
    direcciones: tuple[Ubicacion, ...] = ()
    atributos: dict = Field(default_factory=dict)
    motivos: tuple[Motivo, ...] = Field(min_length=1)
    discrepancias: tuple[Texto, ...] = ()
    puntaje: float | None = Field(default=None, allow_inf_nan=False)
    escala_puntaje: Codigo | None = None
    algoritmo_version: Codigo

    @model_validator(mode="after")
    def escala_explicita(self):
        if (self.puntaje is None) != (self.escala_puntaje is None):
            raise ValueError("Puntaje y escala deben declararse juntos")
        if self.escala_puntaje == "0-1" and not 0 <= self.puntaje <= 1:
            raise ValueError("Puntaje fuera de escala")
        return self


class Advertencia(DTO):
    codigo: Codigo
    descripcion: Texto
    cobertura_id: UUID | None = None


class Hallazgo(DTO):
    id: UUID
    cobertura_id: UUID | None = None
    codigo: Codigo
    descripcion: Texto
    referencia_raw: Texto


class ErrorConsulta(DTO):
    codigo: Codigo
    mensaje: Texto
    correlacion_id: UUID
    reintentable: bool


class Evidencia(DTO):
    id: UUID
    tipo: Literal["INFORME_INTERNO", "MANIFIESTO", "RESPUESTA_ORIGINAL", "PDF_PROVEEDOR", "CAPTURA_PROVEEDOR"]
    estado: Literal["PENDIENTE", "DISPONIBLE", "NO_DISPONIBLE", "ERROR_INTEGRIDAD"]
    # Solo CAPTURA_PROVEEDOR: código de la fuente a la que pertenece la captura de pantalla.
    fuente_codigo: Codigo | None = None
    sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    creada_en: AwareDatetime
    generador_version: Codigo | None = None

    @model_validator(mode="after")
    def hash_disponible(self):
        if self.estado == "DISPONIBLE" and not self.sha256:
            raise ValueError("Evidencia disponible requiere hash")
        return self


class ResultadoProveedorV2(DTO):
    """Resultado técnico previo a la custodia de informes por el servicio común."""
    version_contrato: Literal["2.0"] = "2.0"
    consulta_id: UUID
    implementacion: Implementacion
    proveedor: Codigo
    estado_ejecucion: Estado
    conclusion_busqueda: Conclusion | None
    cobertura: tuple[Cobertura, ...]
    candidatos: tuple[Candidato, ...] = ()
    hallazgos_no_estructurados: tuple[Hallazgo, ...] = ()
    advertencias: tuple[Advertencia, ...] = ()
    criterios_no_aplicados: tuple[Advertencia, ...] = ()
    fecha_inicio: AwareDatetime
    fecha_fin: AwareDatetime | None = None
    error: ErrorConsulta | None = None

    @model_validator(mode="after")
    def invariantes(self):
        pendiente = self.estado_ejecucion in {Estado.PENDIENTE, Estado.EN_CURSO}
        if pendiente:
            if self.conclusion_busqueda is not None or self.fecha_fin is not None:
                raise ValueError("Consulta pendiente no tiene conclusión ni fecha final")
        else:
            if self.fecha_fin is None or self.conclusion_busqueda is None:
                raise ValueError("Resultado terminal requiere conclusión y fecha final")
            if self.fecha_fin < self.fecha_inicio:
                raise ValueError("Fecha final anterior al inicio")
        if self.estado_ejecucion in {Estado.PARCIAL, Estado.FALLIDA, Estado.INDETERMINADA}:
            if self.conclusion_busqueda != Conclusion.NO_CONCLUYENTE:
                raise ValueError("Cobertura incompleta no permite concluir ausencia o coincidencia completa")
        if self.estado_ejecucion == Estado.COMPLETADA:
            if self.implementacion == Implementacion.DESHABILITADO or self.error is not None:
                raise ValueError("Modo deshabilitado o error no puede producir resultado completo")
            requeridas = [c for c in self.cobertura if c.requerida]
            if not requeridas or any(c.estado != "CONSULTADA" for c in requeridas):
                raise ValueError("Resultado completo exige toda la cobertura requerida")
            esperada = (Conclusion.CON_CANDIDATOS if self.candidatos or self.hallazgos_no_estructurados
                        else Conclusion.SIN_CANDIDATOS)
            if self.conclusion_busqueda != esperada:
                raise ValueError("Conclusión incompatible con candidatos/hallazgos")
        ids = {c.id for c in self.cobertura}
        if len(ids) != len(self.cobertura):
            raise ValueError("Cobertura duplicada")
        referencias = [c.cobertura_id for c in self.candidatos]
        referencias += [h.cobertura_id for h in self.hallazgos_no_estructurados if h.cobertura_id]
        referencias += [a.cobertura_id for a in (*self.advertencias, *self.criterios_no_aplicados)
                        if a.cobertura_id]
        if any(ref not in ids for ref in referencias):
            raise ValueError("Referencia a cobertura ajena")
        if self.implementacion == Implementacion.ARCHIVOS:
            if any(c.registro_id is None for c in self.candidatos):
                raise ValueError("Candidato local requiere registro de origen")
            for c in self.cobertura:
                if c.estado == "CONSULTADA" and not (c.version_id and c.hash_contenido
                                                     and c.fuente_codigo and c.revision_activa is not None):
                    raise ValueError("Archivos requiere versión, hash, fuente y revisión")
        if self.implementacion == Implementacion.SIMULADO:
            if not any(a.codigo == "SIMULADO" for a in self.advertencias):
                raise ValueError("Simulación debe estar marcada")
        return self


class ConsultaV2(ResultadoProveedorV2):
    """Contrato público de F3. F1 no fabrica una evidencia ni un cierre persistido."""
    contexto: Annotated[ContextoExpediente | ContextoIndependiente, Field(discriminator="tipo")]
    criterio: Criterio
    grupo_id: UUID | None = None
    fase: Literal["ADMISION", "BUSQUEDA", "PREPARANDO_EVIDENCIA", "CERRANDO", "FINALIZADA"]
    evidencias: tuple[Evidencia, ...] = ()

    @model_validator(mode="after")
    def cierre_con_evidencia(self):
        if self.estado_ejecucion in {Estado.COMPLETADA, Estado.PARCIAL}:
            informes = [e for e in self.evidencias
                        if e.tipo == "INFORME_INTERNO" and e.estado == "DISPONIBLE"]
            if len(informes) != 1:
                raise ValueError("Cierre exige un informe interno disponible")
        return self
