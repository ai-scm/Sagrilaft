"""fechas_representante_date

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-08

Cambio 4 del rediseño de esquema SAGRILAFT: cambia fecha_expedicion y
fecha_nacimiento de texto libre a DATE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CAMPOS_FECHA = ("fecha_expedicion", "fecha_nacimiento")


def _crear_funcion_parseo_fecha() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION _sagrilaft_parse_fecha_colombia(valor text)
    RETURNS date
    LANGUAGE plpgsql
    AS $$
    DECLARE
        limpio text;
        mes integer;
    BEGIN
        IF valor IS NULL OR btrim(valor) = '' THEN
            RETURN NULL;
        END IF;

        limpio := btrim(valor);

        IF limpio ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN
            RETURN limpio::date;
        END IF;

        IF lower(limpio) ~ '^\\d{1,2}-(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-\\d{4}$' THEN
            mes := CASE lower(split_part(limpio, '-', 2))
                WHEN 'ene' THEN 1
                WHEN 'feb' THEN 2
                WHEN 'mar' THEN 3
                WHEN 'abr' THEN 4
                WHEN 'may' THEN 5
                WHEN 'jun' THEN 6
                WHEN 'jul' THEN 7
                WHEN 'ago' THEN 8
                WHEN 'sep' THEN 9
                WHEN 'oct' THEN 10
                WHEN 'nov' THEN 11
                WHEN 'dic' THEN 12
            END;
            RETURN make_date(
                split_part(limpio, '-', 3)::integer,
                mes,
                split_part(limpio, '-', 1)::integer
            );
        END IF;

        RETURN NULL;
    EXCEPTION WHEN others THEN
        RETURN NULL;
    END;
    $$;
    """)


def _eliminar_funcion_parseo_fecha() -> None:
    op.execute("DROP FUNCTION IF EXISTS _sagrilaft_parse_fecha_colombia(text)")


def upgrade() -> None:
    _crear_funcion_parseo_fecha()
    for campo in _CAMPOS_FECHA:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.String(),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using=f"_sagrilaft_parse_fecha_colombia({campo})",
        )
    _eliminar_funcion_parseo_fecha()


def downgrade() -> None:
    for campo in _CAMPOS_FECHA:
        op.alter_column(
            "formularios",
            campo,
            existing_type=sa.Date(),
            type_=sa.String(),
            existing_nullable=True,
            postgresql_using=f"{campo}::text",
        )
