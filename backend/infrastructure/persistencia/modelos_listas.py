"""Modelos del catálogo e historial de listas. Sin lógica de consulta ni importación."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistencia.database import Base

DATOS = JSON().with_variant(JSONB(), "postgresql")


def instante_actual():
    return datetime.now(timezone.utc)


class IdentidadRegistro:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=instante_actual, nullable=False)


class FuenteLista(IdentidadRegistro, Base):
    __tablename__ = "fuente_lista"
    codigo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(200))
    organismo: Mapped[str] = mapped_column(String(200))
    url_oficial: Mapped[str] = mapped_column(Text)


class PoliticaListas(IdentidadRegistro, Base):
    __tablename__ = "politica_listas"
    __table_args__ = (UniqueConstraint("codigo", "version", name="uq_politica_listas_version"),)
    codigo: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    parametros: Mapped[dict] = mapped_column(DATOS)
    huella: Mapped[str] = mapped_column(String(64))
    aprobador_emisor: Mapped[str] = mapped_column(String(500))
    aprobador_sujeto: Mapped[str] = mapped_column(String(200))


class ArchivoFuente(IdentidadRegistro, Base):
    __tablename__ = "archivo_fuente"
    __table_args__ = (
        CheckConstraint("tamano_bytes >= 0", name="ck_archivo_fuente_tamano"),
        CheckConstraint("length(huella) = 64", name="ck_archivo_fuente_huella"),
    )
    clave: Mapped[str] = mapped_column(String(500), unique=True)
    nombre_recibido: Mapped[str] = mapped_column(String(500))
    tipo_contenido: Mapped[str] = mapped_column(String(100))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    huella: Mapped[str] = mapped_column(String(64))
    archivo_padre_id: Mapped[UUID | None] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))


class EsquemaFuente(IdentidadRegistro, Base):
    __tablename__ = "esquema_fuente"
    __table_args__ = (UniqueConstraint("fuente_id", "id", name="uq_esquema_fuente_origen"),)
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    archivo_id: Mapped[UUID] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))
    formato: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(64))
    aprobado: Mapped[bool] = mapped_column(Boolean, default=False)


class RecepcionFuente(IdentidadRegistro, Base):
    __tablename__ = "recepcion_fuente"
    __table_args__ = (
        UniqueConstraint("fuente_id", "id", name="uq_recepcion_fuente_origen"),
        CheckConstraint("estado IN ('PENDIENTE','RECIBIDA','FALLIDA')", name="ck_recepcion_estado"),
        CheckConstraint("estado <> 'RECIBIDA' OR archivo_id IS NOT NULL", name="ck_recepcion_archivo"),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    archivo_id: Mapped[UUID | None] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    url_declarada: Mapped[str] = mapped_column(Text)
    descargado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")


class VersionFuente(IdentidadRegistro, Base):
    __tablename__ = "version_fuente"
    __table_args__ = (
        UniqueConstraint("fuente_id", "id", name="uq_version_fuente_origen"),
        UniqueConstraint("fuente_id", "huella_contenido", "formato", "esquema_id", "version_importador", "version_normalizador", "generacion", name="uq_version_representacion"),
        ForeignKeyConstraint(["fuente_id", "recepcion_id"], ["recepcion_fuente.fuente_id", "recepcion_fuente.id"], ondelete="RESTRICT", name="fk_version_recepcion_origen"),
        ForeignKeyConstraint(["fuente_id", "esquema_id"], ["esquema_fuente.fuente_id", "esquema_fuente.id"], ondelete="RESTRICT", name="fk_version_esquema_origen"),
        CheckConstraint("estado IN ('EN_CONSTRUCCION','VALIDA','BLOQUEADA')", name="ck_version_estado"),
        CheckConstraint("generacion >= 0 AND cantidad_registros >= 0", name="ck_version_conteos"),
        ForeignKeyConstraint(["fuente_id", "reconstruye_version_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_version_reconstruccion"),
        CheckConstraint("(generacion=0 AND reconstruye_version_id IS NULL) OR (generacion>0 AND reconstruye_version_id IS NOT NULL AND motivo_reconstruccion IS NOT NULL)", name="ck_version_reconstruccion"),
        CheckConstraint("estado <> 'VALIDA' OR (manifiesto IS NOT NULL AND cantidad_registros > 0)", name="ck_version_sellada"),
        Index("ix_version_fuente_estado", "fuente_id", "estado"),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    recepcion_id: Mapped[UUID] = mapped_column(Uuid)
    esquema_id: Mapped[UUID] = mapped_column(Uuid)
    archivo_raiz_id: Mapped[UUID] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))
    archivo_contenido_id: Mapped[UUID] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))
    reconstruye_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    motivo_reconstruccion: Mapped[str | None] = mapped_column(Text)
    formato: Mapped[str] = mapped_column(String(64))
    version_importador: Mapped[str] = mapped_column(String(64))
    version_normalizador: Mapped[str] = mapped_column(String(64))
    huella_contenido: Mapped[str] = mapped_column(String(64))
    generacion: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(30), default="EN_CONSTRUCCION")
    cantidad_registros: Mapped[int] = mapped_column(Integer, default=0)
    manifiesto: Mapped[dict | None] = mapped_column(DATOS)
    publicada_en: Mapped[str | None] = mapped_column(String(100))
    origen_fecha: Mapped[str] = mapped_column(String(30), default="DESCONOCIDA")


class RegistroLista(IdentidadRegistro, Base):
    __tablename__ = "registro_lista"
    __table_args__ = (
        UniqueConstraint("version_id", "uid_original", name="uq_registro_version_uid"),
        UniqueConstraint("version_id", "id", name="uq_registro_version_id"),
    )
    version_id: Mapped[UUID] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    uid_original: Mapped[str] = mapped_column(String(200))
    tipo_sujeto: Mapped[str] = mapped_column(String(30))
    contenido_original: Mapped[dict] = mapped_column(DATOS)
    huella_semantica: Mapped[str] = mapped_column(String(64))


class AtributoDeRegistro(IdentidadRegistro):
    registro_id: Mapped[UUID] = mapped_column(ForeignKey("registro_lista.id", ondelete="RESTRICT"))
    ordinal: Mapped[int] = mapped_column(Integer)


class NombreRegistro(AtributoDeRegistro, Base):
    __tablename__ = "nombre_registro"
    __table_args__ = (UniqueConstraint("registro_id", "ordinal", name="uq_nombre_ordinal"), Index("ix_nombre_normalizado", "normalizado"))
    original: Mapped[str] = mapped_column(Text)
    normalizado: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(30))
    atributos: Mapped[dict] = mapped_column(DATOS, default=dict)


class IdentificadorRegistro(AtributoDeRegistro, Base):
    __tablename__ = "identificador_registro"
    __table_args__ = (UniqueConstraint("registro_id", "ordinal", name="uq_identificador_ordinal"), Index("ix_identificador_busqueda", "tipo", "pais_emisor", "normalizado"))
    tipo: Mapped[str] = mapped_column(String(64))
    original: Mapped[str] = mapped_column(Text)
    normalizado: Mapped[str] = mapped_column(Text)
    pais_emisor: Mapped[str | None] = mapped_column(String(10))
    atributos: Mapped[dict] = mapped_column(DATOS, default=dict)


class DireccionRegistro(AtributoDeRegistro, Base):
    __tablename__ = "direccion_registro"
    __table_args__ = (UniqueConstraint("registro_id", "ordinal", name="uq_direccion_ordinal"),)
    original: Mapped[dict] = mapped_column(DATOS)
    normalizada: Mapped[dict] = mapped_column(DATOS)


class AtributoRegistro(AtributoDeRegistro, Base):
    __tablename__ = "atributo_registro"
    __table_args__ = (UniqueConstraint("registro_id", "ordinal", name="uq_atributo_ordinal"),)
    tipo: Mapped[str] = mapped_column(String(100))
    valor: Mapped[dict] = mapped_column(DATOS)
    referencia_original: Mapped[str] = mapped_column(Text)


class RelacionRegistro(IdentidadRegistro, Base):
    __tablename__ = "relacion_registro"
    __table_args__ = (
        Index("ix_relacion_registro_origen", "registro_origen_id"),
        ForeignKeyConstraint(["version_id", "registro_origen_id"], ["registro_lista.version_id", "registro_lista.id"], ondelete="RESTRICT", name="fk_relacion_origen"),
        ForeignKeyConstraint(["version_id", "registro_destino_id"], ["registro_lista.version_id", "registro_lista.id"], ondelete="RESTRICT", name="fk_relacion_destino"),
    )
    version_id: Mapped[UUID] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    registro_origen_id: Mapped[UUID] = mapped_column(Uuid)
    registro_destino_id: Mapped[UUID | None] = mapped_column(Uuid)
    identificador_destino: Mapped[str] = mapped_column(Text)
    ambito_destino: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(100))
    atributos: Mapped[dict] = mapped_column(DATOS, default=dict)


class IntentoImportacion(IdentidadRegistro, Base):
    __tablename__ = "intento_importacion"
    __table_args__ = (CheckConstraint("numero_control >= 0", name="ck_importacion_control"),)
    recepcion_id: Mapped[UUID] = mapped_column(ForeignKey("recepcion_fuente.id", ondelete="RESTRICT"))
    version_id: Mapped[UUID | None] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    estado: Mapped[str] = mapped_column(String(30))
    fase: Mapped[str] = mapped_column(String(30))
    numero_control: Mapped[int] = mapped_column(BigInteger, default=0)
    concesion_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    punto_reanudacion: Mapped[dict] = mapped_column(DATOS, default=dict)
    informe: Mapped[dict | None] = mapped_column(DATOS)
    error: Mapped[str | None] = mapped_column(Text)


class ComparacionVersion(IdentidadRegistro, Base):
    __tablename__ = "comparacion_version"
    __table_args__ = (
        UniqueConstraint("fuente_id", "id", name="uq_comparacion_origen"),
        ForeignKeyConstraint(["fuente_id", "base_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_comparacion_base"),
        ForeignKeyConstraint(["fuente_id", "destino_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_comparacion_destino"),
        CheckConstraint("revision_base >= 0", name="ck_comparacion_revision"),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    base_id: Mapped[UUID | None] = mapped_column(Uuid)
    destino_id: Mapped[UUID] = mapped_column(Uuid)
    revision_base: Mapped[int] = mapped_column(BigInteger)
    version_comparador: Mapped[str] = mapped_column(String(64))
    informe: Mapped[dict] = mapped_column(DATOS)
    huella: Mapped[str] = mapped_column(String(64))


class RevisionComparacion(IdentidadRegistro, Base):
    solicitud_id: Mapped[UUID | None] = mapped_column(ForeignKey("solicitud_administrativa_lista.id", ondelete="RESTRICT"))
    __tablename__ = "revision_comparacion"
    __table_args__ = (
        UniqueConstraint("comparacion_id", "id", name="uq_revision_comparacion_id"),
        CheckConstraint("decision IN ('APROBADA','RECHAZADA','REVOCADA')", name="ck_revision_comparacion_decision"),
        ForeignKeyConstraint(["comparacion_id", "revoca_revision_id"], ["revision_comparacion.comparacion_id", "revision_comparacion.id"], ondelete="RESTRICT", name="fk_revision_revocada"),
    )
    comparacion_id: Mapped[UUID] = mapped_column(ForeignKey("comparacion_version.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(20))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    motivo: Mapped[str] = mapped_column(Text)
    revoca_revision_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)


class FuenteVersionActiva(Base):
    __tablename__ = "fuente_version_activa"
    __table_args__ = (
        ForeignKeyConstraint(["fuente_id", "version_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_activa_misma_fuente"),
        CheckConstraint("revision >= 0", name="ck_activa_revision"),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"), primary_key=True)
    version_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision: Mapped[int] = mapped_column(BigInteger, default=0)


class EventoActivacion(IdentidadRegistro, Base):
    solicitud_id: Mapped[UUID | None] = mapped_column(ForeignKey("solicitud_administrativa_lista.id", ondelete="RESTRICT"), unique=True)
    __tablename__ = "evento_activacion"
    __table_args__ = (
        UniqueConstraint("fuente_id", "revision_nueva", name="uq_activacion_revision"),
        UniqueConstraint("actor_emisor", "actor_sujeto", "fuente_id", "clave_idempotencia", name="uq_activacion_peticion"),
        ForeignKeyConstraint(["fuente_id", "anterior_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_evento_anterior"),
        ForeignKeyConstraint(["fuente_id", "destino_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_evento_destino"),
        ForeignKeyConstraint(["comparacion_id", "aprobacion_id"], ["revision_comparacion.comparacion_id", "revision_comparacion.id"], ondelete="RESTRICT", name="fk_evento_aprobacion"),
        CheckConstraint("revision_nueva = revision_anterior + 1", name="ck_evento_salto_revision"),
        CheckConstraint("tipo IN ('ACTIVACION','REVERSION')", name="ck_evento_tipo"),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    anterior_id: Mapped[UUID | None] = mapped_column(Uuid)
    destino_id: Mapped[UUID] = mapped_column(Uuid)
    comparacion_id: Mapped[UUID] = mapped_column(Uuid)
    aprobacion_id: Mapped[UUID] = mapped_column(Uuid)
    revision_anterior: Mapped[int] = mapped_column(BigInteger)
    revision_nueva: Mapped[int] = mapped_column(BigInteger)
    tipo: Mapped[str] = mapped_column(String(20))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    motivo: Mapped[str] = mapped_column(Text)
    clave_idempotencia: Mapped[str] = mapped_column(String(128))
    huella_peticion: Mapped[str] = mapped_column(String(64))
    politica_id: Mapped[UUID] = mapped_column(ForeignKey("politica_listas.id", ondelete="RESTRICT"))


class EventoVersion(IdentidadRegistro, Base):
    __tablename__ = "evento_version"
    version_id: Mapped[UUID] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    estado_anterior: Mapped[str] = mapped_column(String(30))
    estado_nuevo: Mapped[str] = mapped_column(String(30))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    motivo: Mapped[str] = mapped_column(Text)


class ComprobacionFuente(IdentidadRegistro, Base):
    __tablename__ = "comprobacion_fuente"
    __table_args__ = (ForeignKeyConstraint(["fuente_id", "version_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_comprobacion_version"),)
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    version_id: Mapped[UUID | None] = mapped_column(Uuid)
    archivo_id: Mapped[UUID] = mapped_column(ForeignKey("archivo_fuente.id", ondelete="RESTRICT"))
    resultado: Mapped[str] = mapped_column(String(30))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    url_declarada: Mapped[str] = mapped_column(Text)


class ConsultaLista(IdentidadRegistro, Base):
    __tablename__ = "consulta_lista"
    __table_args__ = (
        UniqueConstraint("actor_emisor", "actor_sujeto", "ambito_idempotencia", "clave_idempotencia", name="uq_consulta_peticion"),
        CheckConstraint("estado IN ('PENDIENTE','EN_CURSO','COMPLETADA','PARCIAL','FALLIDA','INDETERMINADA')", name="ck_consulta_estado"),
        CheckConstraint("implementacion IN ('simulado','archivos','externo')", name="ck_consulta_implementacion"),
        CheckConstraint("(expediente_id IS NOT NULL AND sujeto_rol IS NOT NULL AND sujeto_rol IN ('CONTRAPARTE','REPRESENTANTE')) OR (expediente_id IS NULL AND sujeto_rol IS NULL AND motivo IS NOT NULL AND length(trim(motivo)) >= 10)", name="ck_consulta_contexto"),
        CheckConstraint("(estado IN ('PENDIENTE','EN_CURSO') AND conclusion IS NULL AND finalizada_en IS NULL) OR (estado IN ('COMPLETADA','PARCIAL','FALLIDA','INDETERMINADA') AND conclusion IS NOT NULL AND finalizada_en IS NOT NULL)", name="ck_consulta_cierre"),
        CheckConstraint("estado NOT IN ('PARCIAL','FALLIDA','INDETERMINADA') OR conclusion = 'NO_CONCLUYENTE'", name="ck_consulta_no_concluyente"),
        CheckConstraint("conclusion IS NULL OR conclusion IN ('SIN_CANDIDATOS','CON_CANDIDATOS','NO_CONCLUYENTE')", name="ck_consulta_conclusion"),
        CheckConstraint("finalizada_en IS NULL OR finalizada_en >= creado_en", name="ck_consulta_fechas"),
        Index("ix_consulta_expediente_fecha", "expediente_id", "creado_en"),
        ForeignKeyConstraint(["grupo_id", "actor_emisor", "actor_sujeto", "expediente_id"],
            ["grupo_consulta_lista.id", "grupo_consulta_lista.actor_emisor", "grupo_consulta_lista.actor_sujeto", "grupo_consulta_lista.expediente_id"],
            name="fk_consulta_grupo", ondelete="RESTRICT", deferrable=True, initially="IMMEDIATE"),
        CheckConstraint("grupo_id IS NULL OR expediente_id IS NOT NULL", name="ck_grupo_con_expediente"),
    )
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    expediente_id: Mapped[str | None] = mapped_column(ForeignKey("formularios.id", ondelete="RESTRICT"))
    sujeto_rol: Mapped[str | None] = mapped_column(String(30))
    grupo_id: Mapped[UUID | None] = mapped_column(Uuid)
    consulta_previa_id: Mapped[UUID | None] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    motivo: Mapped[str | None] = mapped_column(Text)
    ambito_idempotencia: Mapped[str] = mapped_column(String(200))
    clave_idempotencia: Mapped[str] = mapped_column(String(128))
    huella_peticion: Mapped[str] = mapped_column(String(64))
    implementacion: Mapped[str] = mapped_column(String(20))
    proveedor: Mapped[str] = mapped_column(String(64))
    version_contrato: Mapped[str] = mapped_column(String(20))
    criterio_original: Mapped[dict] = mapped_column(DATOS)
    manifiesto: Mapped[dict] = mapped_column(DATOS)
    politica_id: Mapped[UUID | None] = mapped_column(ForeignKey("politica_listas.id", ondelete="RESTRICT"))
    estado: Mapped[str] = mapped_column(String(30), default="PENDIENTE")
    conclusion: Mapped[str | None] = mapped_column(String(30))
    resultado: Mapped[dict | None] = mapped_column(DATOS)
    finalizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsultaFuente(IdentidadRegistro, Base):
    __tablename__ = "consulta_fuente"
    __table_args__ = (
        UniqueConstraint("consulta_id", "id", name="uq_cobertura_consulta"),
        UniqueConstraint("consulta_id", "id", "version_id", name="uq_cobertura_version"),
        UniqueConstraint("consulta_id", "fuente_id", name="uq_cobertura_fuente"),
        ForeignKeyConstraint(["fuente_id", "version_id"], ["version_fuente.fuente_id", "version_fuente.id"], ondelete="RESTRICT", name="fk_cobertura_version"),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    fuente_id: Mapped[UUID | None] = mapped_column(ForeignKey("fuente_lista.id", ondelete="RESTRICT"))
    version_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_activa: Mapped[int | None] = mapped_column(BigInteger)
    nombre_origen: Mapped[str] = mapped_column(Text)
    version_externa: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(30))
    requerida: Mapped[bool] = mapped_column(Boolean, default=True)
    detalle: Mapped[dict] = mapped_column(DATOS, default=dict)


class CoincidenciaLista(IdentidadRegistro, Base):
    __tablename__ = "coincidencia_lista"
    __table_args__ = (
        UniqueConstraint("consulta_id", "id", name="uq_coincidencia_consulta"),
        ForeignKeyConstraint(["consulta_id", "consulta_fuente_id"], ["consulta_fuente.consulta_id", "consulta_fuente.id"], ondelete="RESTRICT", name="fk_coincidencia_cobertura"),
        ForeignKeyConstraint(["consulta_id", "consulta_fuente_id", "version_id"], ["consulta_fuente.consulta_id", "consulta_fuente.id", "consulta_fuente.version_id"], ondelete="RESTRICT", name="fk_coincidencia_version_fijada"),
        ForeignKeyConstraint(["version_id", "registro_id"], ["registro_lista.version_id", "registro_lista.id"], ondelete="RESTRICT", name="fk_coincidencia_registro"),
        CheckConstraint("(version_id IS NULL) = (registro_id IS NULL)", name="ck_coincidencia_origen"),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    consulta_fuente_id: Mapped[UUID] = mapped_column(Uuid)
    version_id: Mapped[UUID | None] = mapped_column(Uuid)
    registro_id: Mapped[UUID | None] = mapped_column(Uuid)
    identificador_externo: Mapped[str | None] = mapped_column(Text)
    datos_candidato: Mapped[dict] = mapped_column(DATOS)


class HallazgoProveedor(IdentidadRegistro, Base):
    __tablename__ = "hallazgo_proveedor"
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    contenido: Mapped[dict] = mapped_column(DATOS)


class EvidenciaConsulta(IdentidadRegistro, Base):
    __tablename__ = "evidencia_consulta"
    __table_args__ = (
        UniqueConstraint("consulta_id", "tipo", "clave", name="uq_evidencia_objeto"),
        CheckConstraint("length(huella) = 64 AND tamano_bytes >= 0", name="ck_evidencia_integridad"),
        Index("uq_evidencia_informe", "consulta_id", unique=True, postgresql_where=text("tipo = 'INFORME_INTERNO'"), sqlite_where=text("tipo = 'INFORME_INTERNO'")),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    tipo: Mapped[str] = mapped_column(String(30))
    clave: Mapped[str] = mapped_column(String(500))  # puede repetirse entre consultas (migración o65e78f901ab)
    huella: Mapped[str] = mapped_column(String(64))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    tipo_contenido: Mapped[str] = mapped_column(String(100))
    version_generador: Mapped[str] = mapped_column(String(64))
    fuente_codigo: Mapped[str | None] = mapped_column(String(64))  # solo capturas del proveedor (migración n54c67d890eb)


class RevisionCumplimiento(IdentidadRegistro, Base):
    __tablename__ = "revision_cumplimiento"
    __table_args__ = (
        UniqueConstraint("consulta_id", "id", name="uq_revision_cumplimiento_consulta"),
        ForeignKeyConstraint(["consulta_id", "coincidencia_id"], ["coincidencia_lista.consulta_id", "coincidencia_lista.id"], ondelete="RESTRICT", name="fk_revision_coincidencia"),
        ForeignKeyConstraint(["consulta_id", "revision_previa_id"], ["revision_cumplimiento.consulta_id", "revision_cumplimiento.id"], ondelete="RESTRICT", name="fk_revision_previa"),
        CheckConstraint("resultado IN ('DESCARTADA','IDENTIDAD_CORROBORADA','REQUIERE_INFORMACION')", name="ck_revision_resultado"),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    coincidencia_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_previa_id: Mapped[UUID | None] = mapped_column(Uuid)
    resultado: Mapped[str] = mapped_column(String(40))
    justificacion: Mapped[str] = mapped_column(Text)
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))


class EventoConsulta(IdentidadRegistro, Base):
    __tablename__ = "evento_consulta"
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"))
    tipo: Mapped[str] = mapped_column(String(100))
    detalle: Mapped[dict] = mapped_column(DATOS)
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))


class TrabajoConsulta(IdentidadRegistro, Base):
    __tablename__ = "trabajo_consulta"
    __table_args__ = (
        CheckConstraint("numero_control >= 0", name="ck_trabajo_control"),
        Index("ix_trabajo_concesion", "fase", "concesion_hasta"),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"), unique=True)
    fase: Mapped[str] = mapped_column(String(30), default="ADMISION")
    numero_control: Mapped[int] = mapped_column(BigInteger, default=0)
    concesion_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_latido: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class BorradorConsulta(IdentidadRegistro, Base):
    __tablename__ = "borrador_consulta"
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"), unique=True)
    resultado: Mapped[dict] = mapped_column(DATOS)
    huella: Mapped[str] = mapped_column(String(64))

    informe_clave: Mapped[str | None] = mapped_column(String(500))
    informe_huella: Mapped[str | None] = mapped_column(String(64))
    informe_tamano: Mapped[int | None] = mapped_column(BigInteger)


class ProgresoConsultaExterna(IdentidadRegistro, Base):
    """Etapa del protocolo externo entre pasadas del trabajador (ver migración l32a45b678c9)."""
    __tablename__ = "progreso_consulta_externa"
    __table_args__ = (
        CheckConstraint("etapa IN ('POR_LANZAR','LANZANDO','ESPERANDO','DESCARGANDO_PDF','TERMINADA')", name="ck_progreso_etapa"),
        CheckConstraint("etapa <> 'ESPERANDO' OR jobid IS NOT NULL", name="ck_progreso_jobid"),
        CheckConstraint("recargas >= 0", name="ck_progreso_recargas"),
        CheckConstraint("huella_respuesta IS NULL OR length(huella_respuesta) = 64", name="ck_progreso_huella"),
    )
    consulta_id: Mapped[UUID] = mapped_column(ForeignKey("consulta_lista.id", ondelete="RESTRICT"), unique=True, nullable=False)
    etapa: Mapped[str] = mapped_column(String(20), nullable=False)
    jobid: Mapped[str | None] = mapped_column(String(64))
    reporte_id: Mapped[str | None] = mapped_column(String(64))
    recargas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    huella_respuesta: Mapped[str | None] = mapped_column(String(64))
    respuesta_filtrada: Mapped[dict | None] = mapped_column(DATOS)
    verificacion_documento: Mapped[dict | None] = mapped_column(DATOS)  # migración m43b56c789da


class RitmoProveedor(Base):
    """Último lanzamiento por proveedor, compartido entre trabajadores."""
    __tablename__ = "ritmo_proveedor"
    proveedor: Mapped[str] = mapped_column(String(64), primary_key=True)
    ultimo_lanzamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# Permite registrar únicamente estas tablas sin acoplar la migración a modelos futuros.
TABLAS_LISTAS = tuple(clase.__table__ for clase in (
    FuenteLista, PoliticaListas, ArchivoFuente, EsquemaFuente, RecepcionFuente, VersionFuente,
    RegistroLista, NombreRegistro, IdentificadorRegistro, DireccionRegistro, AtributoRegistro,
    RelacionRegistro, IntentoImportacion, ComparacionVersion, RevisionComparacion,
    FuenteVersionActiva, EventoActivacion, EventoVersion, ComprobacionFuente, ConsultaLista,
    ConsultaFuente, CoincidenciaLista, HallazgoProveedor, EvidenciaConsulta,
    RevisionCumplimiento, EventoConsulta, TrabajoConsulta, BorradorConsulta,
    ProgresoConsultaExterna, RitmoProveedor,
))
