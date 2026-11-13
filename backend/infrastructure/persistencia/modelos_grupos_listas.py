"""Reserva durable de una consulta de contraparte y representante."""
from uuid import UUID
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.persistencia.database import Base
from infrastructure.persistencia.modelos_listas import DATOS, IdentidadRegistro


class GrupoConsultaLista(IdentidadRegistro, Base):
    __tablename__ = "grupo_consulta_lista"
    __table_args__ = (UniqueConstraint("actor_emisor", "actor_sujeto", "expediente_id", "clave", name="uq_grupo_listas_peticion"),
        UniqueConstraint("id", "actor_emisor", "actor_sujeto", "expediente_id", name="uq_grupo_listas_contexto"))
    actor_emisor: Mapped[str] = mapped_column(String(500))
    actor_sujeto: Mapped[str] = mapped_column(String(200))
    expediente_id: Mapped[str] = mapped_column(ForeignKey("formularios.id", ondelete="RESTRICT"))
    clave: Mapped[str] = mapped_column(String(128))
    huella: Mapped[str] = mapped_column(String(64))
    respuesta: Mapped[dict] = mapped_column(DATOS)
