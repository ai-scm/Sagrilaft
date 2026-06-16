"""add_snapshot_datos_documentos

Migración puente para bases existentes que ya registran esta revisión.
Normaliza la columna del snapshot estructurado asociado a cada PDF versionado.

Revision ID: 4524054a8711
Revises: d5e6f7a8b9c0
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "4524054a8711"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'datos_snapshot'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'snapshot_datos'
            ) THEN
                ALTER TABLE documentos_adjuntos
                RENAME COLUMN datos_snapshot TO snapshot_datos;

            ELSIF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'snapshot_datos'
            ) THEN
                ALTER TABLE documentos_adjuntos
                ADD COLUMN snapshot_datos TEXT;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'datos_snapshot'
            ) AND EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'snapshot_datos'
            ) THEN
                UPDATE documentos_adjuntos
                SET snapshot_datos = datos_snapshot
                WHERE snapshot_datos IS NULL
                  AND datos_snapshot IS NOT NULL;

                ALTER TABLE documentos_adjuntos
                DROP COLUMN datos_snapshot;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'snapshot_datos'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'datos_snapshot'
            ) THEN
                ALTER TABLE documentos_adjuntos
                RENAME COLUMN snapshot_datos TO datos_snapshot;

            ELSIF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'documentos_adjuntos'
                  AND column_name = 'snapshot_datos'
            ) THEN
                UPDATE documentos_adjuntos
                SET datos_snapshot = snapshot_datos
                WHERE datos_snapshot IS NULL
                  AND snapshot_datos IS NOT NULL;

                ALTER TABLE documentos_adjuntos
                DROP COLUMN snapshot_datos;
            END IF;
        END $$;
        """
    )
