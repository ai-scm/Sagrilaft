"""Control de escritura por versión e historial de lotes sintéticos."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index, Integer, Float, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.persistencia.database import Base
from infrastructure.persistencia.modelos_listas import IdentidadRegistro


class RecepcionVersionLista(IdentidadRegistro, Base):
    __tablename__ = 'recepcion_version_lista'
    __table_args__ = (
        UniqueConstraint('intento_id', name='uq_recepcion_version_intento'),
        ForeignKeyConstraint(['fuente_id', 'recepcion_id'], ['recepcion_fuente.fuente_id', 'recepcion_fuente.id'], ondelete='RESTRICT'),
        ForeignKeyConstraint(['fuente_id', 'version_id'], ['version_fuente.fuente_id', 'version_fuente.id'], ondelete='RESTRICT'),
        Index('ix_recepcion_version_version', 'version_id'),
    )
    intento_id: Mapped[UUID] = mapped_column(ForeignKey('intento_importacion.id', ondelete='RESTRICT'))
    intento_previo_id: Mapped[UUID | None] = mapped_column(ForeignKey('intento_importacion.id', ondelete='RESTRICT'))
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id', ondelete='RESTRICT'))
    recepcion_id: Mapped[UUID] = mapped_column(ForeignKey('recepcion_fuente.id', ondelete='RESTRICT'))
    version_id: Mapped[UUID] = mapped_column(ForeignKey('version_fuente.id', ondelete='RESTRICT'))


class ControlImportacionVersion(Base):
    __tablename__ = 'control_importacion_version'
    __table_args__ = (
        CheckConstraint('numero_control >= 1 AND reclamaciones BETWEEN 1 AND 3 AND ordinal_confirmado >= 0 AND segundos_consumidos >= 0', name='ck_control_importacion'),
        Index('ix_control_importacion_concesion', 'concesion_hasta'),
    )
    version_id: Mapped[UUID] = mapped_column(ForeignKey('version_fuente.id', ondelete='RESTRICT'), primary_key=True)
    intento_id: Mapped[UUID] = mapped_column(ForeignKey('intento_importacion.id', ondelete='RESTRICT'))
    numero_control: Mapped[int] = mapped_column(Integer)
    reclamaciones: Mapped[int] = mapped_column(Integer)
    revision_datos: Mapped[int] = mapped_column(Integer, default=0)
    ordinal_confirmado: Mapped[int] = mapped_column(Integer, default=0)
    segundos_consumidos: Mapped[float] = mapped_column(Float, default=0)
    ultima_actividad: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    concesion_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoteImportacionLista(IdentidadRegistro, Base):
    __tablename__ = 'lote_importacion_lista'
    __table_args__ = (
        UniqueConstraint('version_id', 'desde', name='uq_lote_importacion_desde'),
        CheckConstraint('desde > 0 AND hasta >= desde AND numero_control > 0 AND length(huella)=64', name='ck_lote_importacion'),
        Index('ix_lote_importacion_version', 'version_id'),
    )
    version_id: Mapped[UUID] = mapped_column(ForeignKey('control_importacion_version.version_id', ondelete='RESTRICT'))
    intento_id: Mapped[UUID] = mapped_column(ForeignKey('intento_importacion.id', ondelete='RESTRICT'))
    numero_control: Mapped[int] = mapped_column(Integer)
    desde: Mapped[int] = mapped_column(Integer)
    hasta: Mapped[int] = mapped_column(Integer)
    huella: Mapped[str] = mapped_column(String(64))
