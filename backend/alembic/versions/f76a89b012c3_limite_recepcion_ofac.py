"""Alinea el límite de recepción OFAC; conserva el límite sintético y todas las comprobaciones."""
from alembic import op
import sqlalchemy as sa

revision = 'f76a89b012c3'
down_revision = 'e65f78a901b2'
branch_labels = None
depends_on = None

FUNCION = """CREATE OR REPLACE FUNCTION comprobar_cierre_recepcion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE identificador uuid; reserva reserva_recepcion_lista; recepcion recepcion_fuente;
    BEGIN
      IF TG_TABLE_NAME='intento_importacion' THEN
        IF EXISTS(SELECT 1 FROM reserva_recepcion_lista WHERE intento_importacion_id=NEW.id AND recepcion_id<>NEW.recepcion_id) THEN
          RAISE EXCEPTION 'Trabajo de recepción no reasignable'; END IF;
      END IF;
      IF TG_TABLE_NAME='recepcion_fuente' THEN identificador=NEW.id;
      ELSE identificador=NEW.recepcion_id; END IF;
      SELECT * INTO reserva FROM reserva_recepcion_lista WHERE recepcion_id=identificador;
      IF NOT FOUND THEN RETURN NULL; END IF;
      SELECT * INTO recepcion FROM recepcion_fuente WHERE id=identificador;
      IF recepcion.estado='RECIBIDA' THEN
        IF reserva.intento_importacion_id IS NULL OR reserva.concesion_hasta IS NOT NULL
          OR NOT EXISTS(SELECT 1 FROM intento_importacion WHERE id=reserva.intento_importacion_id AND recepcion_id=identificador)
          OR NOT EXISTS(SELECT 1 FROM archivo_fuente WHERE id=recepcion.archivo_id
            AND clave=huella AND huella=reserva.metadatos->>'huella_declarada' AND tamano_bytes>0 AND tamano_bytes<={limite})
          OR NOT EXISTS(SELECT 1 FROM evento_recepcion_lista WHERE recepcion_id=identificador AND tipo='RECIBIDA'
            AND detalle->>'archivo_id'=recepcion.archivo_id::text
            AND detalle->>'intento_id'=reserva.intento_importacion_id::text
            AND detalle->>'sha256'=reserva.metadatos->>'huella_declarada') THEN
          RAISE EXCEPTION 'Cierre de recepción incompleto o inconsistente'; END IF;
      ELSIF reserva.intento_importacion_id IS NOT NULL OR recepcion.archivo_id IS NOT NULL THEN
        RAISE EXCEPTION 'Recepción sin confirmar con referencias definitivas';
      END IF;
      RETURN NULL;
    END $$"""


def upgrade():
    op.execute(FUNCION.format(limite="CASE WHEN reserva.metadatos->>'formato' IN ('OFAC_ADVANCED_XML_V3','OFAC_ADVANCED_ZIP_V3')\n              AND EXISTS(SELECT 1 FROM fuente_lista WHERE id=reserva.fuente_id AND codigo='ofac_sdn')\n              THEN 268435456 ELSE 104857600 END"))


def downgrade():
    if op.get_bind().execute(sa.text("""SELECT EXISTS(
        SELECT 1 FROM reserva_recepcion_lista r JOIN recepcion_fuente f ON f.id=r.recepcion_id
        JOIN archivo_fuente a ON a.id=f.archivo_id WHERE a.tamano_bytes>104857600)""")).scalar():
        raise RuntimeError('No se reduce el límite con originales mayores de 100 MiB en el historial')
    op.execute(FUNCION.format(limite='104857600'))
