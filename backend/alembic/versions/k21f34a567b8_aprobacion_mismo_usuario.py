"""Permite cargar y aprobar con el mismo usuario; conserva la auditoría."""
from alembic import op

revision = "k21f34a567b8"
down_revision = "j10e23f456a7"
branch_labels = None
depends_on = None

FUNCIONES_ANTERIORES = """
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

CREATE OR REPLACE FUNCTION listas_validar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
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
"""

FUNCIONES_VIGENTES = """
CREATE OR REPLACE FUNCTION listas_validar_aprobacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    IF (NEW.decision='REVOCADA') <> (NEW.revoca_revision_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Revocación sin aprobación de origen';
    END IF;
    IF NEW.decision='REVOCADA' AND NOT EXISTS(SELECT 1 FROM revision_comparacion WHERE id=NEW.revoca_revision_id AND decision='APROBADA') THEN
        RAISE EXCEPTION 'Solo se revoca una aprobación';
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION listas_validar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
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
"""

def upgrade():
    op.execute(FUNCIONES_VIGENTES)


def downgrade():
    # Restaura la restricción para operaciones futuras, sin reescribir el historial.
    op.execute(FUNCIONES_ANTERIORES)
