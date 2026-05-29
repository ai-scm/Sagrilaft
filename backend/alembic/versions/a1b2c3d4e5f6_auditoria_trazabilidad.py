"""auditoria_trazabilidad

Añade infraestructura de trazabilidad documental y auditoría:
  - Tabla eventos_formulario: log inmutable append-only de transiciones de estado
  - Columnas de versionado y hash en documentos_adjuntos
  - Trigger PostgreSQL para detectar cambios directos en BD (bypass de la aplicación)

Revision ID: a1b2c3d4e5f6
Revises: 88f43ed37c21
Create Date: 2026-05-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '88f43ed37c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tabla de eventos (append-only audit log) ─────────────────────────────
    op.create_table(
        'eventos_formulario',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('formulario_id', sa.String(), sa.ForeignKey('formularios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo_evento', sa.String(length=60), nullable=False),
        sa.Column('estado_anterior', sa.String(length=50), nullable=True),
        sa.Column('estado_nuevo', sa.String(length=50), nullable=False),
        sa.Column('actor_id', sa.String(length=255), nullable=True),
        sa.Column('actor_tipo', sa.String(length=20), nullable=False, server_default='SISTEMA'),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_eventos_formulario_form_id', 'eventos_formulario', ['formulario_id'])
    op.create_index('ix_eventos_formulario_form_created', 'eventos_formulario',
                    ['formulario_id', 'created_at'])

    # ── Columnas de versionado y hash en documentos_adjuntos ─────────────────
    op.add_column('documentos_adjuntos',
                  sa.Column('version_numero', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('documentos_adjuntos',
                  sa.Column('version_anterior_id', sa.String(),
                            sa.ForeignKey('documentos_adjuntos.id'), nullable=True))
    op.add_column('documentos_adjuntos',
                  sa.Column('subido_por', sa.String(length=255), nullable=True))
    op.add_column('documentos_adjuntos',
                  sa.Column('hash_sha256', sa.String(length=64), nullable=True))

    # ── Trigger: detecta cambios de estado hechos directamente en BD ─────────
    # La aplicación pone SET LOCAL sagrilaft.from_app = '1' antes de cada UPDATE.
    # Si esa variable no está, el cambio vino de fuera de la aplicación → se registra.
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_audit_estado_formulario()
        RETURNS TRIGGER AS $$
        BEGIN
            IF current_setting('sagrilaft.from_app', true) = '1' THEN
                RETURN NEW;
            END IF;
            IF OLD.estado IS DISTINCT FROM NEW.estado THEN
                INSERT INTO eventos_formulario(
                    formulario_id, tipo_evento, estado_anterior, estado_nuevo,
                    actor_id, actor_tipo
                ) VALUES (
                    NEW.id, 'CAMBIO_DIRECTO_BD', OLD.estado, NEW.estado,
                    'BYPASS_APLICACION', 'DB_DIRECTO'
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER tg_audit_estado
        AFTER UPDATE OF estado ON formularios
        FOR EACH ROW EXECUTE FUNCTION fn_audit_estado_formulario();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tg_audit_estado ON formularios;")
    op.execute("DROP FUNCTION IF EXISTS fn_audit_estado_formulario();")

    op.drop_column('documentos_adjuntos', 'hash_sha256')
    op.drop_column('documentos_adjuntos', 'subido_por')
    op.drop_column('documentos_adjuntos', 'version_anterior_id')
    op.drop_column('documentos_adjuntos', 'version_numero')

    op.drop_index('ix_eventos_formulario_form_created', 'eventos_formulario')
    op.drop_index('ix_eventos_formulario_form_id', 'eventos_formulario')
    op.drop_table('eventos_formulario')
