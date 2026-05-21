"""add_numero_correccion

Añade el contador de rondas de corrección al formulario.
Usa IF NOT EXISTS para ser idempotente si la columna ya existe en la BD.

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on:    Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE formularios
        ADD COLUMN IF NOT EXISTS numero_correccion INTEGER NOT NULL DEFAULT 0
    """)


def downgrade() -> None:
    op.drop_column('formularios', 'numero_correccion')
