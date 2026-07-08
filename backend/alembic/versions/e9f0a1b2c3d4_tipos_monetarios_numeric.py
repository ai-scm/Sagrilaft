"""tipos_monetarios_numeric

Revision ID: e9f0a1b2c3d4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-08

Cambio 3 del rediseño de esquema SAGRILAFT: cambia los 6 campos monetarios
del formulario de FLOAT a NUMERIC(18,2), manteniendo el contrato JSON como
numero hacia el frontend.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAMPOS_MONETARIOS = (
    "ingresos_mensuales",
    "otros_ingresos",
    "egresos_mensuales",
    "total_activos",
    "total_pasivos",
    "patrimonio",
)


def upgrade() -> None:
    for campo in _CAMPOS_MONETARIOS:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
            postgresql_using=f"{campo}::numeric(18,2)",
        )


def downgrade() -> None:
    for campo in _CAMPOS_MONETARIOS:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
            postgresql_using=f"{campo}::double precision",
        )
