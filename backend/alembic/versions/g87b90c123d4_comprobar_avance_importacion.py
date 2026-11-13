"""Comprueba el avance al cambiar registros/lotes; evita repetir conteos por cada atributo."""
from alembic import op

revision = 'g87b90c123d4'
down_revision = 'f76a89b012c3'
branch_labels = None
depends_on = None


def upgrade():
    # La revisión de datos sigue aumentando por cada escritura. Solo se evita que sus
    # cambios, que no alteran el número de registros, encolen el mismo conteo al commit.
    op.execute('DROP TRIGGER comprobar_avance ON control_importacion_version')
    op.execute('''CREATE OR REPLACE FUNCTION listas_comprobar_avance() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE identificador uuid; nuevo uuid; anterior uuid; ordinal integer;
    BEGIN
      IF TG_TABLE_NAME='registro_lista' THEN
        IF TG_OP<>'DELETE' THEN nuevo=NEW.version_id; END IF;
        IF TG_OP<>'INSERT' THEN anterior=OLD.version_id; END IF;
      ELSE nuevo=NEW.version_id; END IF;
      FOR identificador IN SELECT DISTINCT v FROM unnest(ARRAY[nuevo,anterior]) AS v WHERE v IS NOT NULL LOOP
        SELECT ordinal_confirmado INTO ordinal FROM control_importacion_version WHERE version_id=identificador;
        IF NOT FOUND THEN CONTINUE; END IF;
        IF ordinal<>COALESCE((SELECT max(hasta) FROM lote_importacion_lista WHERE version_id=identificador),0)
          OR ordinal<>(SELECT count(*) FROM registro_lista WHERE version_id=identificador) THEN
          RAISE EXCEPTION 'Avance y lotes no coinciden'; END IF;
      END LOOP;
      RETURN NULL;
    END $$''')
    op.execute('''CREATE CONSTRAINT TRIGGER comprobar_avance AFTER INSERT ON control_importacion_version
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_avance()''')
    op.execute('''CREATE CONSTRAINT TRIGGER comprobar_avance_actualizacion AFTER UPDATE ON control_importacion_version
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        WHEN (OLD.ordinal_confirmado IS DISTINCT FROM NEW.ordinal_confirmado)
        EXECUTE FUNCTION listas_comprobar_avance()''')
    # Un INSERT/DELETE/traslado sin actualizar el avance también debe fallar al confirmar.
    op.execute('''CREATE CONSTRAINT TRIGGER comprobar_avance_registros AFTER INSERT OR UPDATE OR DELETE ON registro_lista
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_avance()''')


def downgrade():
    op.execute('DROP TRIGGER comprobar_avance_registros ON registro_lista')
    op.execute('DROP TRIGGER comprobar_avance_actualizacion ON control_importacion_version')
    op.execute('DROP TRIGGER comprobar_avance ON control_importacion_version')
    op.execute('''CREATE OR REPLACE FUNCTION listas_comprobar_avance() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE identificador uuid; ordinal integer;
    BEGIN
      identificador=NEW.version_id;
      SELECT ordinal_confirmado INTO ordinal FROM control_importacion_version WHERE version_id=identificador;
      IF ordinal<>COALESCE((SELECT max(hasta) FROM lote_importacion_lista WHERE version_id=identificador),0)
        OR ordinal<>(SELECT count(*) FROM registro_lista WHERE version_id=identificador) THEN
        RAISE EXCEPTION 'Avance y lotes no coinciden'; END IF;
      RETURN NULL;
    END $$''')
    op.execute('''CREATE CONSTRAINT TRIGGER comprobar_avance AFTER INSERT OR UPDATE ON control_importacion_version
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_avance()''')
