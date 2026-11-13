"""Indexa la lectura de relaciones por registro durante el cotejo de importación."""
from alembic import op

revision = 'h98c01d234e5'
down_revision = 'g87b90c123d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_relacion_registro_origen','relacion_registro',['registro_origen_id'])


def downgrade():
    op.drop_index('ix_relacion_registro_origen',table_name='relacion_registro')
