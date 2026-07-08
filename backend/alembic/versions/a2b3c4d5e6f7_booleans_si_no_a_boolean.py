"""booleans_si_no_a_boolean

Revision ID: a2b3c4d5e6f7
Revises: f0a1b2c3d4e5
Create Date: 2026-07-08

Cambio 6 del rediseño de esquema SAGRILAFT: cambia 8 campos "si"/"no"
del formulario a BOOLEAN NOT NULL DEFAULT false.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAMPOS_BOOLEANOS = (
    "realiza_operaciones_moneda_extranjera",
    "autorretenedor",
    "gran_contribuyente",
    "entidad_sin_animo_lucro",
    "retencion_ica",
    "impuesto_ica",
    "entidad_oficial",
    "exento_retencion_fuente",
)


def upgrade() -> None:
    for campo in _CAMPOS_BOOLEANOS:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.String(),
            type_=sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            postgresql_using=f"lower(btrim(coalesce({campo}, ''))) IN ('si', 'sí', 'true', '1')",
        )


def downgrade() -> None:
    for campo in _CAMPOS_BOOLEANOS:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.Boolean(),
            type_=sa.String(),
            nullable=True,
            server_default=None,
            postgresql_using=f"CASE WHEN {campo} THEN 'si' ELSE 'no' END",
        )
