"""Representación derivada de búsqueda; nunca sustituye los registros importados."""
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistencia.database import Base
from infrastructure.persistencia.modelos_listas import IdentidadRegistro


class GeneracionBusqueda(IdentidadRegistro, Base):
    __tablename__ = "generacion_busqueda_lista"
    __table_args__ = (
        UniqueConstraint("version_id", "id", name="uq_generacion_version"),
        UniqueConstraint("version_id", "adaptador_version", "normalizacion_version", "catalogo_huella", name="uq_generacion_receta"),
        CheckConstraint("estado IN ('PREPARANDO','LISTA')", name="ck_generacion_estado"),
        CheckConstraint("cantidad_registros > 0 AND cantidad_consultables BETWEEN 0 AND cantidad_registros", name="ck_generacion_conteos"),
        CheckConstraint("length(huella)=64 AND length(catalogo_huella)=64", name="ck_generacion_huellas"),
    )
    version_id: Mapped[UUID] = mapped_column(ForeignKey("version_fuente.id", ondelete="RESTRICT"))
    adaptador_version: Mapped[str] = mapped_column(String(64))
    normalizacion_version: Mapped[str] = mapped_column(String(64))
    catalogo_huella: Mapped[str] = mapped_column(String(64))
    estado: Mapped[str] = mapped_column(String(20), default="PREPARANDO")
    cantidad_registros: Mapped[int] = mapped_column(Integer)
    cantidad_consultables: Mapped[int] = mapped_column(Integer)
    huella: Mapped[str] = mapped_column(String(64))


class RegistroBusquedaPersistido(Base):
    __tablename__ = "registro_busqueda_lista"
    __table_args__ = (
        ForeignKeyConstraint(["version_id", "generacion_id"], ["generacion_busqueda_lista.version_id", "generacion_busqueda_lista.id"], ondelete="RESTRICT", name="fk_busqueda_generacion_version"),
        ForeignKeyConstraint(["version_id", "registro_id"], ["registro_lista.version_id", "registro_lista.id"], ondelete="RESTRICT", name="fk_busqueda_registro_version"),
        CheckConstraint("(datos IS NOT NULL AND motivo_exclusion IS NULL) OR (datos IS NULL AND motivo_exclusion IS NOT NULL)", name="ck_busqueda_exclusion"),
        CheckConstraint("length(huella)=64", name="ck_busqueda_huella"),
    )
    generacion_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    registro_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(Uuid)
    datos: Mapped[dict | None] = mapped_column(JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"))
    motivo_exclusion: Mapped[str | None] = mapped_column(String(64))
    huella: Mapped[str] = mapped_column(String(64))


class TerminoBusqueda(Base):
    __tablename__ = "termino_busqueda_lista"
    __table_args__ = (
        ForeignKeyConstraint(["generacion_id", "registro_id"], ["registro_busqueda_lista.generacion_id", "registro_busqueda_lista.registro_id"], ondelete="RESTRICT", name="fk_termino_registro"),
        CheckConstraint("clase IN ('NOMBRE','IDENTIFICADOR') AND ordinal >= 0 AND length(huella_valor)=64", name="ck_termino_busqueda"),
        Index("ix_termino_generacion_valor", "generacion_id", "clase", "huella_valor"),
    )
    generacion_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    registro_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    clase: Mapped[str] = mapped_column(String(20), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    huella_valor: Mapped[str] = mapped_column(String(64))


TABLAS_BUSQUEDA = tuple(c.__table__ for c in (GeneracionBusqueda, RegistroBusquedaPersistido, TerminoBusqueda))
