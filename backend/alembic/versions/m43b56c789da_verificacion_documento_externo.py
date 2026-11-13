"""Resultado de la verificación previa del documento en la consulta externa.

Antes de consultar listas, el trabajador valida el NIT (cámaras de comercio) o la cédula
de extranjería (Migración Colombia) con Tusdatos. El resultado se guarda aquí para no
repetir la verificación en la siguiente pasada y para avisar al revisor si el documento
no está vigente. Solo guarda el estado y los avisos del proveedor, nunca nombres.
"""
from alembic import op

revision = "m43b56c789da"
down_revision = "l32a45b678c9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE progreso_consulta_externa ADD COLUMN verificacion_documento JSONB")


def downgrade():
    op.execute("ALTER TABLE progreso_consulta_externa DROP COLUMN verificacion_documento")
