"""correo_destinatario_obligatorio

Revision ID: f8a9b0c1d2e3
Revises: c7a1c1a65662
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "c7a1c1a65662"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "accesos_manuales",
        "correo_destinatario",
        existing_type=sa.String(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "accesos_manuales",
        "correo_destinatario",
        existing_type=sa.String(),
        nullable=True,
    )
