"""Una misma evidencia custodiada puede pertenecer a varias consultas.

La custodia nombra cada archivo por su huella: dos imágenes idénticas son el mismo objeto.
Hasta ahora `evidencia_consulta.clave` era única en toda la tabla, así que si dos consultas
recibían la misma captura de Tusdatos (siempre en el sandbox; en producción, por ejemplo, al
forzar una consulta del mismo documento), la segunda se quedaba sin su evidencia. Se quita
esa unicidad global. Se conserva `uq_evidencia_objeto (consulta_id, tipo, clave)`: una
consulta no registra dos veces el mismo objeto. Los objetos custodiados no se borran nunca,
así que compartirlos no pone en riesgo a otra consulta.
"""
from alembic import op

revision = "o65e78f901ab"
down_revision = "n54c67d890eb"
branch_labels = None
depends_on = None

# La restricción se creó sin nombre (`UNIQUE (clave)`): se busca por su definición.
_BORRAR_UNICA_CLAVE = """
DO $$
DECLARE nombre text;
BEGIN
    SELECT c.conname INTO nombre FROM pg_constraint c
    WHERE c.conrelid = 'evidencia_consulta'::regclass AND c.contype = 'u'
      AND c.conkey = ARRAY[(SELECT attnum FROM pg_attribute
                            WHERE attrelid = 'evidencia_consulta'::regclass AND attname = 'clave')]::smallint[];
    IF nombre IS NULL THEN
        RAISE EXCEPTION 'No se encontró la restricción única de evidencia_consulta.clave';
    END IF;
    EXECUTE format('ALTER TABLE evidencia_consulta DROP CONSTRAINT %I', nombre);
END $$;
"""


def upgrade():
    op.execute(_BORRAR_UNICA_CLAVE)


def downgrade():
    conexion = op.get_bind()
    repetidas = conexion.exec_driver_sql(
        "SELECT count(*) FROM (SELECT clave FROM evidencia_consulta GROUP BY clave HAVING count(*) > 1) r").scalar()
    if repetidas:
        raise RuntimeError("Hay evidencias compartidas entre consultas: no se restaura la unicidad global de la clave")
    op.execute("ALTER TABLE evidencia_consulta ADD CONSTRAINT evidencia_consulta_clave_key UNIQUE (clave)")
