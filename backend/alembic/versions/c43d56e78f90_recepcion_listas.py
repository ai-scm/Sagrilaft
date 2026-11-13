"""Recepción manual y auditoría, sin modificar migraciones históricas."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = 'c43d56e78f90'
down_revision = 'b32c45d67e89'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('reserva_recepcion_lista',
        sa.Column('recepcion_id', sa.Uuid(), sa.ForeignKey('recepcion_fuente.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('fuente_id', sa.Uuid(), sa.ForeignKey('fuente_lista.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_emisor', sa.String(500), nullable=False), sa.Column('actor_sujeto', sa.String(200), nullable=False),
        sa.Column('clave', sa.String(128), nullable=False), sa.Column('huella_peticion', sa.String(64), nullable=False),
        sa.Column('metadatos', JSONB(), nullable=False), sa.Column('numero_control', sa.Integer(), nullable=False),
        sa.Column('intentos', sa.Integer(), nullable=False), sa.Column('concesion_hasta', sa.DateTime(timezone=True)),
        sa.Column('intento_importacion_id', sa.Uuid(), sa.ForeignKey('intento_importacion.id', ondelete='RESTRICT'), unique=True),
        sa.UniqueConstraint('actor_emisor','actor_sujeto','fuente_id','clave', name='uq_reserva_recepcion'),
        sa.CheckConstraint('numero_control >= 0 AND intentos >= 0 AND intentos <= 3', name='ck_reserva_control'))
    op.create_table('evento_recepcion_lista',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recepcion_id', sa.Uuid(), sa.ForeignKey('recepcion_fuente.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_emisor', sa.String(500), nullable=False), sa.Column('actor_sujeto', sa.String(200), nullable=False),
        sa.Column('tipo', sa.String(64), nullable=False), sa.Column('detalle', JSONB(), nullable=False))
    op.execute('CREATE TRIGGER conservar_evento_recepcion BEFORE UPDATE OR DELETE ON evento_recepcion_lista FOR EACH ROW EXECUTE FUNCTION listas_inmutable()')
    op.execute('''CREATE FUNCTION proteger_reserva_recepcion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r recepcion_fuente;
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'La reserva no se elimina'; END IF;
      SELECT * INTO r FROM recepcion_fuente WHERE id=NEW.recepcion_id;
      IF (r.fuente_id,r.actor_emisor,r.actor_sujeto) IS DISTINCT FROM (NEW.fuente_id,NEW.actor_emisor,NEW.actor_sujeto) THEN
        RAISE EXCEPTION 'Reserva de otro origen'; END IF;
      IF TG_OP='UPDATE' AND ((to_jsonb(NEW)-'numero_control'-'intentos'-'concesion_hasta'-'intento_importacion_id')
        IS DISTINCT FROM (to_jsonb(OLD)-'numero_control'-'intentos'-'concesion_hasta'-'intento_importacion_id')
        OR OLD.intento_importacion_id IS NOT NULL) THEN RAISE EXCEPTION 'Reserva final o identidad inmutable'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER proteger_reserva BEFORE INSERT OR UPDATE OR DELETE ON reserva_recepcion_lista FOR EACH ROW EXECUTE FUNCTION proteger_reserva_recepcion()')

    # Se comprueba al confirmar la transacción, después de todos los INSERT/UPDATE.
    # Solo afecta recepciones del nuevo circuito: el historial anterior de F2 se conserva.
    op.execute("""CREATE FUNCTION comprobar_cierre_recepcion() RETURNS trigger LANGUAGE plpgsql AS $$
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
            AND clave=huella AND huella=reserva.metadatos->>'huella_declarada' AND tamano_bytes>0 AND tamano_bytes<=104857600)
          OR NOT EXISTS(SELECT 1 FROM evento_recepcion_lista WHERE recepcion_id=identificador AND tipo='RECIBIDA'
            AND detalle->>'archivo_id'=recepcion.archivo_id::text
            AND detalle->>'intento_id'=reserva.intento_importacion_id::text
            AND detalle->>'sha256'=reserva.metadatos->>'huella_declarada') THEN
          RAISE EXCEPTION 'Cierre de recepción incompleto o inconsistente'; END IF;
      ELSIF reserva.intento_importacion_id IS NOT NULL OR recepcion.archivo_id IS NOT NULL THEN
        RAISE EXCEPTION 'Recepción sin confirmar con referencias definitivas';
      END IF;
      RETURN NULL;
    END $$""")
    for tabla in ('reserva_recepcion_lista', 'recepcion_fuente', 'intento_importacion'):
        op.execute(f'CREATE CONSTRAINT TRIGGER comprobar_cierre_recepcion AFTER INSERT OR UPDATE ON {tabla} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION comprobar_cierre_recepcion()')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM reserva_recepcion_lista)')).scalar():
        raise RuntimeError('No se revierte recepción con historial')
    for tabla in ('reserva_recepcion_lista', 'recepcion_fuente', 'intento_importacion'):
        op.execute(f'DROP TRIGGER comprobar_cierre_recepcion ON {tabla}')
    op.execute('DROP FUNCTION comprobar_cierre_recepcion()')
    op.drop_table('evento_recepcion_lista')
    op.drop_table('reserva_recepcion_lista')
    op.execute('DROP FUNCTION proteger_reserva_recepcion()')
