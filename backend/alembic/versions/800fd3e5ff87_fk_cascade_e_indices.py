"""fk_cascade_e_indices

Revision ID: 800fd3e5ff87
Revises: a5aed126c881
Create Date: 2026-04-29

Corrige dos problemas heredados de SQLite:

1. ON DELETE CASCADE en las tres FKs hacia formularios.
   SQLite no aplica FKs por defecto, por lo que eliminar un formulario con
   hijos no lanzaba error. PostgreSQL las aplica siempre, rompiendo el cascade
   ORM cuando existen documentos soft-deleted (deleted_at IS NOT NULL) fuera
   del relationship filtrado.

2. Índices en documentos_adjuntos.formulario_id y
   resultados_validacion.formulario_id. PostgreSQL no crea índices
   automáticamente en columnas FK; sin ellos cada lookup hace seq-scan.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "800fd3e5ff87"
down_revision: Union[str, Sequence[str], None] = "a5aed126c881"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Recrear FKs con ON DELETE CASCADE ─────────────────────────────────

    op.drop_constraint(
        "documentos_adjuntos_formulario_id_fkey",
        "documentos_adjuntos",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "documentos_adjuntos_formulario_id_fkey",
        "documentos_adjuntos",
        "formularios",
        ["formulario_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "resultados_validacion_formulario_id_fkey",
        "resultados_validacion",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "resultados_validacion_formulario_id_fkey",
        "resultados_validacion",
        "formularios",
        ["formulario_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "accesos_manuales_formulario_id_fkey",
        "accesos_manuales",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "accesos_manuales_formulario_id_fkey",
        "accesos_manuales",
        "formularios",
        ["formulario_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── 2. Índices en columnas FK sin índice ──────────────────────────────────

    op.create_index(
        "ix_documentos_adjuntos_formulario_id",
        "documentos_adjuntos",
        ["formulario_id"],
    )
    op.create_index(
        "ix_resultados_validacion_formulario_id",
        "resultados_validacion",
        ["formulario_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resultados_validacion_formulario_id", "resultados_validacion")
    op.drop_index("ix_documentos_adjuntos_formulario_id", "documentos_adjuntos")

    op.drop_constraint("accesos_manuales_formulario_id_fkey", "accesos_manuales", type_="foreignkey")
    op.create_foreign_key(
        "accesos_manuales_formulario_id_fkey", "accesos_manuales", "formularios",
        ["formulario_id"], ["id"],
    )

    op.drop_constraint("resultados_validacion_formulario_id_fkey", "resultados_validacion", type_="foreignkey")
    op.create_foreign_key(
        "resultados_validacion_formulario_id_fkey", "resultados_validacion", "formularios",
        ["formulario_id"], ["id"],
    )

    op.drop_constraint("documentos_adjuntos_formulario_id_fkey", "documentos_adjuntos", type_="foreignkey")
    op.create_foreign_key(
        "documentos_adjuntos_formulario_id_fkey", "documentos_adjuntos", "formularios",
        ["formulario_id"], ["id"],
    )
