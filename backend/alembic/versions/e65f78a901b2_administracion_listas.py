"""Solicitudes F5.5; conserva las reglas históricas de F2."""
from alembic import op
import sqlalchemy as sa
revision = 'e65f78a901b2'
down_revision = 'd54e67f890a1'
branch_labels = None
depends_on = None

FUNCIONES_ANTERIORES = """
CREATE OR REPLACE FUNCTION listas_validar_aprobacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; cargador recepcion_fuente;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT r.* INTO cargador FROM recepcion_fuente r JOIN version_fuente v ON v.recepcion_id=r.id WHERE v.id=comparacion.destino_id;
    IF NEW.decision='APROBADA' AND NEW.actor_emisor=cargador.actor_emisor AND NEW.actor_sujeto=cargador.actor_sujeto THEN
        RAISE EXCEPTION 'El cargador no puede aprobar su carga';
    END IF;
    IF (NEW.decision='REVOCADA') <> (NEW.revoca_revision_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Revocación sin aprobación de origen';
    END IF;
    IF NEW.decision='REVOCADA' AND NOT EXISTS(SELECT 1 FROM revision_comparacion WHERE id=NEW.revoca_revision_id AND decision='APROBADA') THEN
        RAISE EXCEPTION 'Solo se revoca una aprobación';
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION listas_validar_evento_activacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; aprobacion revision_comparacion;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT * INTO aprobacion FROM revision_comparacion WHERE id=NEW.aprobacion_id;
    IF comparacion.fuente_id IS DISTINCT FROM NEW.fuente_id OR comparacion.base_id IS DISTINCT FROM NEW.anterior_id
       OR comparacion.destino_id IS DISTINCT FROM NEW.destino_id OR comparacion.revision_base <> NEW.revision_anterior
       OR aprobacion.decision IS DISTINCT FROM 'APROBADA'
       OR EXISTS(SELECT 1 FROM revision_comparacion WHERE revoca_revision_id=NEW.aprobacion_id) THEN
        RAISE EXCEPTION 'Comparación o aprobación no vigente para la activación';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM version_fuente WHERE id=NEW.destino_id AND estado='VALIDA') THEN
        RAISE EXCEPTION 'Destino no válido';
    END IF;
    RETURN NEW;
END $$;

"""
FUNCIONES_COMPATIBLES = """
CREATE OR REPLACE FUNCTION listas_validar_aprobacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; cargador recepcion_fuente;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT r.* INTO cargador FROM recepcion_fuente r JOIN version_fuente v ON v.recepcion_id=r.id WHERE v.id=comparacion.destino_id;
    IF NEW.decision='APROBADA' AND NOT EXISTS (SELECT 1 FROM solicitud_administrativa_lista WHERE id=NEW.solicitud_id AND tipo='REVERSION') AND NEW.actor_emisor=cargador.actor_emisor AND NEW.actor_sujeto=cargador.actor_sujeto THEN
        RAISE EXCEPTION 'El cargador no puede aprobar su carga';
    END IF;
    IF (NEW.decision='REVOCADA') <> (NEW.revoca_revision_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Revocación sin aprobación de origen';
    END IF;
    IF NEW.decision='REVOCADA' AND NOT EXISTS(SELECT 1 FROM revision_comparacion WHERE id=NEW.revoca_revision_id AND decision='APROBADA') THEN
        RAISE EXCEPTION 'Solo se revoca una aprobación';
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION listas_validar_evento_activacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; aprobacion revision_comparacion;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT * INTO aprobacion FROM revision_comparacion WHERE id=NEW.aprobacion_id;
    IF comparacion.fuente_id IS DISTINCT FROM NEW.fuente_id OR comparacion.base_id IS DISTINCT FROM NEW.anterior_id
       OR comparacion.destino_id IS DISTINCT FROM NEW.destino_id OR comparacion.revision_base <> NEW.revision_anterior
       OR aprobacion.decision IS DISTINCT FROM 'APROBADA'
       OR EXISTS(SELECT 1 FROM revision_comparacion WHERE revoca_revision_id=NEW.aprobacion_id) THEN
        RAISE EXCEPTION 'Comparación o aprobación no vigente para la activación';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM version_fuente WHERE id=NEW.destino_id AND estado='VALIDA') THEN
        RAISE EXCEPTION 'Destino no válido';
    END IF;
    RETURN NEW;
END $$;

"""


def upgrade():
    op.execute("""
    CREATE TABLE solicitud_administrativa_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL, fuente_id uuid NOT NULL REFERENCES fuente_lista(id),
      comparacion_id uuid NOT NULL REFERENCES comparacion_version(id), politica_id uuid NOT NULL REFERENCES politica_listas(id),
      tipo varchar(20) NOT NULL CONSTRAINT ck_solicitud_tipo CHECK(tipo IN ('ACTIVACION','REVERSION')),
      actor_emisor varchar(500) NOT NULL CONSTRAINT ck_solicitud_emisor CHECK(length(trim(actor_emisor))>0),
      actor_sujeto varchar(200) NOT NULL CONSTRAINT ck_solicitud_sujeto CHECK(length(trim(actor_sujeto))>0), motivo text NOT NULL CONSTRAINT ck_solicitud_motivo CHECK(length(trim(motivo))>0),
      FOREIGN KEY(fuente_id,comparacion_id) REFERENCES comparacion_version(fuente_id,id));
    CREATE INDEX ix_solicitud_administrativa_lista_comparacion_id ON solicitud_administrativa_lista(comparacion_id);
    CREATE TABLE trabajo_comparacion_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL, fuente_id uuid NOT NULL REFERENCES fuente_lista(id),
      base_id uuid, destino_id uuid NOT NULL, revision_base bigint NOT NULL CONSTRAINT ck_trabajo_comparacion_revision CHECK(revision_base>=0),
      estado varchar(20) NOT NULL CONSTRAINT ck_trabajo_comparacion_estado CHECK(estado IN ('PENDIENTE','COMPLETADO','FALLIDO')), error varchar(64),
      actor_emisor varchar(500) NOT NULL, actor_sujeto varchar(200) NOT NULL,
      CONSTRAINT ck_trabajo_comparacion_error CHECK((estado='FALLIDO')=(error IS NOT NULL)),
      FOREIGN KEY(fuente_id,base_id) REFERENCES version_fuente(fuente_id,id),
      FOREIGN KEY(fuente_id,destino_id) REFERENCES version_fuente(fuente_id,id));
    CREATE INDEX ix_trabajo_comparacion_lista_estado ON trabajo_comparacion_lista(estado);
    CREATE TABLE operacion_administrativa_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL, fuente_id uuid NOT NULL REFERENCES fuente_lista(id),
      actor_emisor varchar(500) NOT NULL, actor_sujeto varchar(200) NOT NULL,
      operacion varchar(40) NOT NULL, clave varchar(128) NOT NULL CONSTRAINT ck_operacion_clave CHECK(length(clave)>0), huella varchar(64) NOT NULL,
      resultado jsonb NOT NULL, CONSTRAINT uq_operacion_administrativa UNIQUE(actor_emisor,actor_sujeto,operacion,clave));
    CREATE TABLE evento_administrativo_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL, fuente_id uuid NOT NULL REFERENCES fuente_lista(id),
      actor_emisor varchar(500) NOT NULL, actor_sujeto varchar(200) NOT NULL, tipo varchar(50) NOT NULL, detalle jsonb NOT NULL);
    CREATE INDEX ix_evento_administrativo_lista_fuente_id ON evento_administrativo_lista(fuente_id);
    ALTER TABLE revision_comparacion ADD COLUMN solicitud_id uuid REFERENCES solicitud_administrativa_lista(id);
    ALTER TABLE evento_activacion ADD COLUMN solicitud_id uuid UNIQUE REFERENCES solicitud_administrativa_lista(id);
    CREATE UNIQUE INDEX uq_decision_solicitud ON revision_comparacion(solicitud_id) WHERE decision IN ('APROBADA','RECHAZADA');
    """)
    op.execute(FUNCIONES_COMPATIBLES)
    op.execute("""
    CREATE FUNCTION listas_comprobar_solicitud_nueva() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE comparacion comparacion_version; puntero fuente_version_activa;
    BEGIN
      SELECT * INTO puntero FROM fuente_version_activa WHERE fuente_id=NEW.fuente_id FOR UPDATE;
      SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id;
      IF comparacion.fuente_id IS DISTINCT FROM NEW.fuente_id
        OR comparacion.base_id IS DISTINCT FROM puntero.version_id OR comparacion.revision_base<>puntero.revision
        OR NOT EXISTS(SELECT 1 FROM trabajo_comparacion_lista WHERE id=comparacion.id AND estado='COMPLETADO')
        THEN RAISE EXCEPTION 'Solicitud requiere comparación completa y vigente'; END IF;
      IF NEW.tipo='REVERSION' AND NOT EXISTS(SELECT 1 FROM evento_activacion WHERE fuente_id=NEW.fuente_id AND destino_id=comparacion.destino_id)
        THEN RAISE EXCEPTION 'La versión nunca estuvo activa'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER comprobar_solicitud BEFORE INSERT ON solicitud_administrativa_lista FOR EACH ROW EXECUTE FUNCTION listas_comprobar_solicitud_nueva();
    CREATE FUNCTION listas_validar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE solicitud solicitud_administrativa_lista; comparacion comparacion_version; aprobacion revision_comparacion;
    BEGIN
      IF NEW.solicitud_id IS NULL THEN
        IF EXISTS(SELECT 1 FROM comparacion_version c JOIN control_importacion_version i ON i.version_id=c.destino_id
                  WHERE c.id=NEW.comparacion_id) THEN RAISE EXCEPTION 'Nueva administración exige solicitud'; END IF;
        RETURN NEW;
      END IF;
      SELECT * INTO solicitud FROM solicitud_administrativa_lista WHERE id=NEW.solicitud_id FOR UPDATE;
      SELECT * INTO comparacion FROM comparacion_version WHERE id=solicitud.comparacion_id;
      IF solicitud.comparacion_id IS DISTINCT FROM NEW.comparacion_id THEN RAISE EXCEPTION 'Solicitud de otra comparación'; END IF;
      IF TG_TABLE_NAME='revision_comparacion' THEN
        IF NEW.decision IN ('APROBADA','RECHAZADA') AND (NEW.actor_emisor,NEW.actor_sujeto)=(solicitud.actor_emisor,solicitud.actor_sujeto)
          THEN RAISE EXCEPTION 'El solicitante no puede decidir'; END IF;
        IF NEW.decision='REVOCADA' THEN
          IF NOT EXISTS(SELECT 1 FROM revision_comparacion WHERE id=NEW.revoca_revision_id AND solicitud_id=solicitud.id AND decision='APROBADA')
            OR EXISTS(SELECT 1 FROM evento_activacion WHERE solicitud_id=solicitud.id)
            THEN RAISE EXCEPTION 'Aprobación no revocable'; END IF;
        END IF;
      ELSE
        SELECT * INTO aprobacion FROM revision_comparacion WHERE id=NEW.aprobacion_id;
        IF aprobacion.solicitud_id IS DISTINCT FROM solicitud.id OR solicitud.tipo<>NEW.tipo
          OR solicitud.politica_id<>NEW.politica_id OR solicitud.fuente_id<>NEW.fuente_id
          OR (NEW.actor_emisor,NEW.actor_sujeto) IS DISTINCT FROM (aprobacion.actor_emisor,aprobacion.actor_sujeto)
          THEN RAISE EXCEPTION 'Ejecución incompatible con solicitud y aprobador'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER validar_solicitud BEFORE INSERT ON revision_comparacion FOR EACH ROW EXECUTE FUNCTION listas_validar_solicitud();
    CREATE TRIGGER validar_solicitud BEFORE INSERT ON evento_activacion FOR EACH ROW EXECUTE FUNCTION listas_validar_solicitud();
    CREATE FUNCTION listas_proteger_trabajo_comparacion() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR OLD.estado<>'PENDIENTE' OR (to_jsonb(NEW)-'estado'-'error')<>(to_jsonb(OLD)-'estado'-'error')
        THEN RAISE EXCEPTION 'Trabajo de comparación inmutable'; END IF;
      IF NEW.estado='COMPLETADO' AND NOT EXISTS(SELECT 1 FROM comparacion_version WHERE id=NEW.id)
        THEN RAISE EXCEPTION 'Comparación incompleta'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER proteger_trabajo BEFORE UPDATE OR DELETE ON trabajo_comparacion_lista FOR EACH ROW EXECUTE FUNCTION listas_proteger_trabajo_comparacion();
    """)
    for tabla in ('solicitud_administrativa_lista','operacion_administrativa_lista','evento_administrativo_lista'):
        op.execute(f'CREATE TRIGGER proteger_{tabla} BEFORE UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_inmutable()')


def downgrade():
    for tabla in ('solicitud_administrativa_lista','trabajo_comparacion_lista','operacion_administrativa_lista','evento_administrativo_lista'):
        if op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {tabla})')).scalar():
            raise RuntimeError('No se revierte administración con historial')
    op.execute('DROP TRIGGER validar_solicitud ON revision_comparacion')
    op.execute('DROP TRIGGER validar_solicitud ON evento_activacion')
    op.execute('DROP FUNCTION listas_validar_solicitud()')
    op.execute(FUNCIONES_ANTERIORES)
    op.execute('ALTER TABLE revision_comparacion DROP COLUMN solicitud_id')
    op.execute('ALTER TABLE evento_activacion DROP COLUMN solicitud_id')
    for tabla in ('evento_administrativo_lista','operacion_administrativa_lista','trabajo_comparacion_lista','solicitud_administrativa_lista'):
        op.drop_table(tabla)
    op.execute('DROP FUNCTION listas_proteger_trabajo_comparacion()')
    op.execute('DROP FUNCTION listas_comprobar_solicitud_nueva()')
