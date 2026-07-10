"""normalizar_datos_condicionales_persona

Revision ID: f2a3b4c5d6e7
Revises: b3c4d5e6f7a8
Create Date: 2026-07-08

Normaliza los bloques condicionales del formulario:
- residencia exclusiva de persona natural
- clasificacion de empresa y regimen tributario exclusiva de persona juridica
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "formulario_persona_natural",
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("direccion_residencia", sa.String(), nullable=True),
        sa.Column("ciudad_residencia", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("formulario_id"),
    )
    op.create_index(
        "ix_formulario_persona_natural_formulario_id",
        "formulario_persona_natural",
        ["formulario_id"],
    )

    op.create_table(
        "formulario_clasificacion_tributaria",
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("actividad_clasificacion", sa.String(), nullable=True),
        sa.Column("actividad_especifica", sa.String(), nullable=True),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("superintendencia", sa.String(), nullable=True),
        sa.Column("responsabilidades_renta", sa.String(), nullable=True),
        sa.Column("autorretenedor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("responsabilidades_iva", sa.String(), nullable=True),
        sa.Column("regimen_iva", sa.String(), nullable=True),
        sa.Column("gran_contribuyente", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entidad_sin_animo_lucro", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retencion_ica", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("impuesto_ica", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entidad_oficial", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("exento_retencion_fuente", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("formulario_id"),
    )
    op.create_index(
        "ix_formulario_clasificacion_tributaria_formulario_id",
        "formulario_clasificacion_tributaria",
        ["formulario_id"],
    )

    op.execute("""
        INSERT INTO formulario_persona_natural (
            formulario_id,
            direccion_residencia,
            ciudad_residencia
        )
        SELECT
            id,
            direccion_residencia,
            ciudad_residencia
        FROM formularios
        WHERE lower(coalesce(tipo_persona, '')) = 'natural'
           OR direccion_residencia IS NOT NULL
           OR ciudad_residencia IS NOT NULL;
    """)

    op.execute("""
        INSERT INTO formulario_clasificacion_tributaria (
            formulario_id,
            actividad_clasificacion,
            actividad_especifica,
            sector,
            superintendencia,
            responsabilidades_renta,
            autorretenedor,
            responsabilidades_iva,
            regimen_iva,
            gran_contribuyente,
            entidad_sin_animo_lucro,
            retencion_ica,
            impuesto_ica,
            entidad_oficial,
            exento_retencion_fuente
        )
        SELECT
            id,
            actividad_clasificacion,
            actividad_especifica,
            sector,
            superintendencia,
            responsabilidades_renta,
            coalesce(autorretenedor, false),
            responsabilidades_iva,
            regimen_iva,
            coalesce(gran_contribuyente, false),
            coalesce(entidad_sin_animo_lucro, false),
            coalesce(retencion_ica, false),
            coalesce(impuesto_ica, false),
            coalesce(entidad_oficial, false),
            coalesce(exento_retencion_fuente, false)
        FROM formularios
        WHERE lower(coalesce(tipo_persona, '')) = 'juridica'
           OR actividad_clasificacion IS NOT NULL
           OR actividad_especifica IS NOT NULL
           OR sector IS NOT NULL
           OR superintendencia IS NOT NULL
           OR responsabilidades_renta IS NOT NULL
           OR responsabilidades_iva IS NOT NULL
           OR regimen_iva IS NOT NULL
           OR autorretenedor IS TRUE
           OR gran_contribuyente IS TRUE
           OR entidad_sin_animo_lucro IS TRUE
           OR retencion_ica IS TRUE
           OR impuesto_ica IS TRUE
           OR entidad_oficial IS TRUE
           OR exento_retencion_fuente IS TRUE;
    """)

    op.drop_column("formularios", "direccion_residencia")
    op.drop_column("formularios", "ciudad_residencia")
    op.drop_column("formularios", "actividad_clasificacion")
    op.drop_column("formularios", "actividad_especifica")
    op.drop_column("formularios", "sector")
    op.drop_column("formularios", "superintendencia")
    op.drop_column("formularios", "responsabilidades_renta")
    op.drop_column("formularios", "autorretenedor")
    op.drop_column("formularios", "responsabilidades_iva")
    op.drop_column("formularios", "regimen_iva")
    op.drop_column("formularios", "gran_contribuyente")
    op.drop_column("formularios", "entidad_sin_animo_lucro")
    op.drop_column("formularios", "retencion_ica")
    op.drop_column("formularios", "impuesto_ica")
    op.drop_column("formularios", "entidad_oficial")
    op.drop_column("formularios", "exento_retencion_fuente")


def downgrade() -> None:
    op.add_column("formularios", sa.Column("direccion_residencia", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("ciudad_residencia", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("actividad_clasificacion", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("actividad_especifica", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("sector", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("superintendencia", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("responsabilidades_renta", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("autorretenedor", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("responsabilidades_iva", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("regimen_iva", sa.String(), nullable=True))
    op.add_column("formularios", sa.Column("gran_contribuyente", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("entidad_sin_animo_lucro", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("retencion_ica", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("impuesto_ica", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("entidad_oficial", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("formularios", sa.Column("exento_retencion_fuente", sa.Boolean(), nullable=False, server_default="false"))

    op.execute("""
        UPDATE formularios f
        SET
            direccion_residencia = n.direccion_residencia,
            ciudad_residencia = n.ciudad_residencia
        FROM formulario_persona_natural n
        WHERE n.formulario_id = f.id;
    """)

    op.execute("""
        UPDATE formularios f
        SET
            actividad_clasificacion = c.actividad_clasificacion,
            actividad_especifica = c.actividad_especifica,
            sector = c.sector,
            superintendencia = c.superintendencia,
            responsabilidades_renta = c.responsabilidades_renta,
            autorretenedor = c.autorretenedor,
            responsabilidades_iva = c.responsabilidades_iva,
            regimen_iva = c.regimen_iva,
            gran_contribuyente = c.gran_contribuyente,
            entidad_sin_animo_lucro = c.entidad_sin_animo_lucro,
            retencion_ica = c.retencion_ica,
            impuesto_ica = c.impuesto_ica,
            entidad_oficial = c.entidad_oficial,
            exento_retencion_fuente = c.exento_retencion_fuente
        FROM formulario_clasificacion_tributaria c
        WHERE c.formulario_id = f.id;
    """)

    op.drop_index(
        "ix_formulario_clasificacion_tributaria_formulario_id",
        table_name="formulario_clasificacion_tributaria",
    )
    op.drop_table("formulario_clasificacion_tributaria")
    op.drop_index(
        "ix_formulario_persona_natural_formulario_id",
        table_name="formulario_persona_natural",
    )
    op.drop_table("formulario_persona_natural")
