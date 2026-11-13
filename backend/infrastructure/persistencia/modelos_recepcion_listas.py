"""Reserva durable y eventos de recepción; no contiene versiones importadas."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, String, Integer, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.persistencia.database import Base
from infrastructure.persistencia.modelos_listas import IdentidadRegistro, DATOS


class ReservaRecepcionLista(Base):
    __tablename__ = 'reserva_recepcion_lista'
    __table_args__ = (
        UniqueConstraint('actor_emisor', 'actor_sujeto', 'fuente_id', 'clave', name='uq_reserva_recepcion'),
        CheckConstraint('numero_control >= 0 AND intentos >= 0 AND intentos <= 3', name='ck_reserva_control'),
    )
    recepcion_id: Mapped[UUID] = mapped_column(ForeignKey('recepcion_fuente.id', ondelete='RESTRICT'), primary_key=True)
    fuente_id: Mapped[UUID] = mapped_column(ForeignKey('fuente_lista.id', ondelete='RESTRICT'))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    clave: Mapped[str] = mapped_column(String(128))
    huella_peticion: Mapped[str] = mapped_column(String(64))
    metadatos: Mapped[dict] = mapped_column(DATOS)
    numero_control: Mapped[int] = mapped_column(Integer, default=0)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    concesion_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intento_importacion_id: Mapped[UUID | None] = mapped_column(ForeignKey('intento_importacion.id', ondelete='RESTRICT'), unique=True)


class EventoRecepcionLista(IdentidadRegistro, Base):
    __tablename__ = 'evento_recepcion_lista'
    recepcion_id: Mapped[UUID] = mapped_column(ForeignKey('recepcion_fuente.id', ondelete='RESTRICT'))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(64))
    detalle: Mapped[dict] = mapped_column(DATOS)
