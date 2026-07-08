"""normalizar_listas_dinamicas

Revision ID: b7e4f2a19c3d
Revises: d62426367da1
Create Date: 2026-07-07

Cambio 1 del rediseño de esquema SAGRILAFT: mueve las 7 listas dinámicas del
formulario (hoy columnas Text con JSON serializado a mano) a tablas 1:N
propias, cada una con FK a formularios(id) ON DELETE CASCADE:

  - junta_directiva              -> formulario_junta_directiva
  - accionistas                  -> formulario_accionistas
  - beneficiario_final           -> formulario_beneficiarios_finales
  - referencias_comerciales      -> formulario_referencias_comerciales
  - referencias_bancarias        -> formulario_referencias_bancarias_declaradas
  - informacion_bancaria_pagos   -> formulario_cuentas_pago
  - tipos_transaccion            -> formulario_tipos_transaccion (tabla de unión)

También elimina `clasificaciones`: columna sin consumidores en backend ni
frontend (confirmado por auditoría de código previa a esta migración).

No hay datos en producción que deban preservarse a la fecha de este cambio,
por lo que no se incluye backfill de filas existentes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4f2a19c3d"
down_revision: Union[str, Sequence[str], None] = "d62426367da1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "formulario_junta_directiva",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("cargo", sa.String(), nullable=True),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("tipo_id", sa.String(), nullable=True),
        sa.Column("numero_id", sa.String(), nullable=True),
        sa.Column("es_pep", sa.String(), nullable=True),
        sa.Column("vinculos_pep", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_junta_directiva_formulario_id",
        "formulario_junta_directiva",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_accionistas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("tipo_id", sa.String(), nullable=True),
        sa.Column("numero_id", sa.String(), nullable=True),
        sa.Column("es_pep", sa.String(), nullable=True),
        sa.Column("vinculos_pep", sa.String(), nullable=True),
        sa.Column("porcentaje", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_accionistas_formulario_id",
        "formulario_accionistas",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_beneficiarios_finales",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=True),
        sa.Column("tipo_id", sa.String(), nullable=True),
        sa.Column("numero_id", sa.String(), nullable=True),
        sa.Column("es_pep", sa.String(), nullable=True),
        sa.Column("vinculos_pep", sa.String(), nullable=True),
        sa.Column("porcentaje", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_beneficiarios_finales_formulario_id",
        "formulario_beneficiarios_finales",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_referencias_comerciales",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("nombre_establecimiento", sa.String(), nullable=True),
        sa.Column("persona_contacto", sa.String(), nullable=True),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("ciudad", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_referencias_comerciales_formulario_id",
        "formulario_referencias_comerciales",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_referencias_bancarias_declaradas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("entidad", sa.String(), nullable=True),
        sa.Column("producto", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_referencias_bancarias_declaradas_formulario_id",
        "formulario_referencias_bancarias_declaradas",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_cuentas_pago",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("entidad_bancaria", sa.String(), nullable=True),
        sa.Column("ciudad_oficina", sa.String(), nullable=True),
        sa.Column("tipo_cuenta", sa.String(), nullable=True),
        sa.Column("numero_cuenta", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_cuentas_pago_formulario_id",
        "formulario_cuentas_pago",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_tipos_transaccion",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_formulario_tipos_transaccion_formulario_id",
        "formulario_tipos_transaccion",
        ["formulario_id"],
    )

    op.drop_column("formularios", "junta_directiva")
    op.drop_column("formularios", "accionistas")
    op.drop_column("formularios", "beneficiario_final")
    op.drop_column("formularios", "referencias_comerciales")
    op.drop_column("formularios", "referencias_bancarias")
    op.drop_column("formularios", "informacion_bancaria_pagos")
    op.drop_column("formularios", "tipos_transaccion")
    op.drop_column("formularios", "clasificaciones")


def downgrade() -> None:
    op.add_column("formularios", sa.Column("clasificaciones", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("tipos_transaccion", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("informacion_bancaria_pagos", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("referencias_bancarias", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("referencias_comerciales", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("beneficiario_final", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("accionistas", sa.Text(), nullable=True))
    op.add_column("formularios", sa.Column("junta_directiva", sa.Text(), nullable=True))

    op.drop_table("formulario_tipos_transaccion")
    op.drop_table("formulario_cuentas_pago")
    op.drop_table("formulario_referencias_bancarias_declaradas")
    op.drop_table("formulario_referencias_comerciales")
    op.drop_table("formulario_beneficiarios_finales")
    op.drop_table("formulario_accionistas")
    op.drop_table("formulario_junta_directiva")
