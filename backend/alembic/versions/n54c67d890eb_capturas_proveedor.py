"""Fuente de cada evidencia del proveedor.

Tusdatos entrega una captura de pantalla por fuente (OFAC, ONU, INTERPOL, Procuraduría…).
Cada captura se custodia como evidencia CAPTURA_PROVEEDOR y esta columna dice de qué fuente
es. El PDF y el informe interno la dejan vacía.
"""
from alembic import op

revision = "n54c67d890eb"
down_revision = "m43b56c789da"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE evidencia_consulta ADD COLUMN fuente_codigo VARCHAR(64)")


def downgrade():
    op.execute("ALTER TABLE evidencia_consulta DROP COLUMN fuente_codigo")
