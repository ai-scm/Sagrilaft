"""normalizar_contactos

Revision ID: c8d9e0f1a2b3
Revises: b7e4f2a19c3d
Create Date: 2026-07-08

Cambio 2 del rediseño de esquema SAGRILAFT: mueve los 8 campos planos
contacto_ordenes_* y contacto_pagos_* a la tabla contactos, manteniendo el
contrato plano en repositorios.py.

No hay datos en producción que deban preservarse a la fecha de este cambio,
por lo que no se incluye backfill de filas existentes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b7e4f2a19c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contactos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("cargo", sa.String(), nullable=True),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("correo", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formulario_id", "tipo", name="uq_contactos_formulario_tipo"),
    )
    op.create_index("ix_contactos_formulario_id", "contactos", ["formulario_id"])

    op.drop_column("formularios", "contacto_ordenes_nombre")
    op.drop_column("formularios", "contacto_ordenes_cargo")
    op.drop_column("formularios", "contacto_ordenes_telefono")
    op.drop_column("formularios", "contacto_ordenes_correo")
    op.drop_column("formularios", "contacto_pagos_nombre")
    op.drop_column("formularios", "contacto_pagos_cargo")
    op.drop_column("formularios", "contacto_pagos_telefono")
    op.drop_column("formularios", "contacto_pagos_correo")


def downgrade() -> None:
    op.add_column("formularios", sa.Column("contacto_pagos_correo", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_pagos_telefono", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_pagos_cargo", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_pagos_nombre", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_ordenes_correo", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_ordenes_telefono", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_ordenes_cargo", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("contacto_ordenes_nombre", sa.String(), nullable=True))

    op.drop_table("contactos")
