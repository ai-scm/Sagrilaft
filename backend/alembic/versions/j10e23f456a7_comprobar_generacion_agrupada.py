"""Comprueba los términos de cada generación en una sola agregación."""
from alembic import op

revision = "j10e23f456a7"
down_revision = "i09d12e345f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE OR REPLACE FUNCTION listas_comprobar_generacion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE g generacion_busqueda_lista;
    BEGIN
      SELECT * INTO g FROM generacion_busqueda_lista WHERE id=NEW.id;
      IF g.estado<>'LISTA' OR g.cantidad_registros<>(SELECT cantidad_registros FROM version_fuente WHERE id=g.version_id)
        OR g.cantidad_registros<>(SELECT count(*) FROM registro_busqueda_lista WHERE generacion_id=g.id)
        OR g.cantidad_consultables<>(SELECT count(*) FROM registro_busqueda_lista WHERE generacion_id=g.id AND motivo_exclusion IS NULL)
      THEN RAISE EXCEPTION 'Generación de búsqueda incompleta'; END IF;
      IF EXISTS (
        SELECT 1 FROM registro_busqueda_lista r
        LEFT JOIN (
          SELECT registro_id,
            count(*) FILTER (WHERE clase='NOMBRE') AS nombres,
            count(*) FILTER (WHERE clase='IDENTIFICADOR') AS identificadores
          FROM termino_busqueda_lista WHERE generacion_id=g.id GROUP BY registro_id
        ) t ON t.registro_id=r.registro_id
        WHERE r.generacion_id=g.id AND r.datos IS NOT NULL AND (
          coalesce(t.nombres,0)<>jsonb_array_length(r.datos->'registro'->'nombres') OR
          coalesce(t.identificadores,0)<>jsonb_array_length(r.datos->'registro'->'identificadores')))
      THEN RAISE EXCEPTION 'Índice de búsqueda incompleto'; END IF;
      RETURN NULL;
    END $$""")


def downgrade():
    op.execute("""CREATE OR REPLACE FUNCTION listas_comprobar_generacion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE g generacion_busqueda_lista;
    BEGIN
      SELECT * INTO g FROM generacion_busqueda_lista WHERE id=NEW.id;
      IF g.estado<>'LISTA' OR g.cantidad_registros<>(SELECT cantidad_registros FROM version_fuente WHERE id=g.version_id)
        OR g.cantidad_registros<>(SELECT count(*) FROM registro_busqueda_lista WHERE generacion_id=g.id)
        OR g.cantidad_consultables<>(SELECT count(*) FROM registro_busqueda_lista WHERE generacion_id=g.id AND motivo_exclusion IS NULL)
      THEN RAISE EXCEPTION 'Generación de búsqueda incompleta'; END IF;
      IF EXISTS (SELECT 1 FROM registro_busqueda_lista r WHERE r.generacion_id=g.id AND r.datos IS NOT NULL AND (
        (SELECT count(*) FROM termino_busqueda_lista t WHERE t.generacion_id=g.id AND t.registro_id=r.registro_id AND t.clase='NOMBRE')
          <>jsonb_array_length(r.datos->'registro'->'nombres') OR
        (SELECT count(*) FROM termino_busqueda_lista t WHERE t.generacion_id=g.id AND t.registro_id=r.registro_id AND t.clase='IDENTIFICADOR')
          <>jsonb_array_length(r.datos->'registro'->'identificadores')))
      THEN RAISE EXCEPTION 'Índice de búsqueda incompleto'; END IF;
      RETURN NULL;
    END $$""")
