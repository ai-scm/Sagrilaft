"""Solicitudes inmutables y trabajos administrativos locales."""
from uuid import UUID
from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, String, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.persistencia.database import Base
from infrastructure.persistencia.modelos_listas import IdentidadRegistro, DATOS


class SolicitudAdministrativaLista(IdentidadRegistro, Base):
    __tablename__ = 'solicitud_administrativa_lista'
    __table_args__ = (
        ForeignKeyConstraint(['fuente_id', 'comparacion_id'], ['comparacion_version.fuente_id', 'comparacion_version.id']),
        CheckConstraint("tipo IN ('ACTIVACION','REVERSION')", name='ck_solicitud_tipo'),
        CheckConstraint('length(trim(actor_emisor))>0', name='ck_solicitud_emisor'),
        CheckConstraint('length(trim(actor_sujeto))>0', name='ck_solicitud_sujeto'),
        CheckConstraint('length(trim(motivo))>0', name='ck_solicitud_motivo'),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id'))
    comparacion_id: Mapped[UUID] = mapped_column(ForeignKey('comparacion_version.id'), index=True)
    politica_id: Mapped[UUID] = mapped_column(ForeignKey('politica_listas.id'))
    tipo: Mapped[str] = mapped_column(String(20))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    motivo: Mapped[str] = mapped_column(Text)


class TrabajoComparacionLista(IdentidadRegistro, Base):
    __tablename__ = 'trabajo_comparacion_lista'
    __table_args__ = (
        ForeignKeyConstraint(['fuente_id','base_id'], ['version_fuente.fuente_id','version_fuente.id']),
        ForeignKeyConstraint(['fuente_id','destino_id'], ['version_fuente.fuente_id','version_fuente.id']),
        CheckConstraint("estado IN ('PENDIENTE','COMPLETADO','FALLIDO')", name='ck_trabajo_comparacion_estado'),
        CheckConstraint('revision_base>=0', name='ck_trabajo_comparacion_revision'),
        CheckConstraint("(estado='FALLIDO')=(error IS NOT NULL)", name='ck_trabajo_comparacion_error'),
    )
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id'))
    base_id: Mapped[UUID | None]
    destino_id: Mapped[UUID]
    revision_base: Mapped[int] = mapped_column(BigInteger)
    estado: Mapped[str] = mapped_column(String(20), default='PENDIENTE', index=True)
    error: Mapped[str | None] = mapped_column(String(64))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))


class OperacionAdministrativaLista(IdentidadRegistro, Base):
    __tablename__ = 'operacion_administrativa_lista'
    __table_args__ = (UniqueConstraint('actor_emisor','actor_sujeto','operacion','clave',name='uq_operacion_administrativa'),
                      CheckConstraint('length(clave)>0', name='ck_operacion_clave'))
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id'))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    operacion: Mapped[str] = mapped_column(String(40))
    clave: Mapped[str] = mapped_column(String(128))
    huella: Mapped[str] = mapped_column(String(64))
    resultado: Mapped[dict] = mapped_column(DATOS)


class EventoAdministrativoLista(IdentidadRegistro, Base):
    __tablename__ = 'evento_administrativo_lista'
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id'), index=True)
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(50))
    detalle: Mapped[dict] = mapped_column(DATOS)
