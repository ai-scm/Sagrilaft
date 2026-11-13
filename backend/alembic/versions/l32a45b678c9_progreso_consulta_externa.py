"""Progreso de consultas externas entre pasadas del trabajador y ritmo de lanzamientos por proveedor.

`progreso_consulta_externa` guarda la etapa del protocolo (antes de lanzar, lanzando,
esperando el resultado, descargando el PDF), el jobid y el id del reporte del proveedor,
el subconjunto de fuentes de interés y la huella de la respuesta completa. Se registra
la etapa LANZANDO antes de llamar al proveedor: si el trabajador cae en esa etapa, la
consulta queda indeterminada y nunca se relanza sola.

`ritmo_proveedor` reparte los lanzamientos entre trabajadores para respetar la espera
mínima que exige el proveedor (Tusdatos: 5 segundos).
"""
from alembic import op

revision = "l32a45b678c9"
down_revision = "k21f34a567b8"
branch_labels = None
depends_on = None

SENTENCIAS = (
    """CREATE TABLE progreso_consulta_externa (
	consulta_id UUID NOT NULL,
	etapa VARCHAR(20) NOT NULL,
	jobid VARCHAR(64),
	reporte_id VARCHAR(64),
	recargas INTEGER NOT NULL,
	vence_en TIMESTAMP WITH TIME ZONE NOT NULL,
	actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	huella_respuesta VARCHAR(64),
	respuesta_filtrada JSONB,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (consulta_id),
	CONSTRAINT ck_progreso_etapa CHECK (etapa IN ('POR_LANZAR','LANZANDO','ESPERANDO','DESCARGANDO_PDF','TERMINADA')),
	CONSTRAINT ck_progreso_jobid CHECK (etapa <> 'ESPERANDO' OR jobid IS NOT NULL),
	CONSTRAINT ck_progreso_recargas CHECK (recargas >= 0),
	CONSTRAINT ck_progreso_huella CHECK (huella_respuesta IS NULL OR length(huella_respuesta) = 64),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    # Igual que los demás hijos de la consulta: no cambia después del cierre.
    """CREATE TRIGGER proteger_progreso_consulta_externa BEFORE INSERT OR UPDATE OR DELETE
	ON progreso_consulta_externa FOR EACH ROW EXECUTE FUNCTION listas_proteger_hijos_consulta()""",
    """CREATE TABLE ritmo_proveedor (
	proveedor VARCHAR(64) NOT NULL,
	ultimo_lanzamiento TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (proveedor)
)""",
)


def upgrade():
    for sentencia in SENTENCIAS:
        op.execute(sentencia)


def downgrade():
    op.execute("DROP TABLE ritmo_proveedor")
    op.execute("DROP TABLE progreso_consulta_externa")
