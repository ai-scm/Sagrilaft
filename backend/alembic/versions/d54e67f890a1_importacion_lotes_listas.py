"""Importación por lotes: vínculos, exclusión por versión y avance durable."""
from alembic import op
import sqlalchemy as sa
revision = 'd54e67f890a1'
down_revision = 'c43d56e78f90'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE recepcion_version_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL,
      intento_id uuid NOT NULL REFERENCES intento_importacion(id) ON DELETE RESTRICT,
      intento_previo_id uuid REFERENCES intento_importacion(id) ON DELETE RESTRICT,
      fuente_id uuid NOT NULL REFERENCES fuente_lista(id) ON DELETE RESTRICT,
      recepcion_id uuid NOT NULL REFERENCES recepcion_fuente(id) ON DELETE RESTRICT,
      version_id uuid NOT NULL REFERENCES version_fuente(id) ON DELETE RESTRICT,
      CONSTRAINT uq_recepcion_version_intento UNIQUE(intento_id),
      FOREIGN KEY(fuente_id,recepcion_id) REFERENCES recepcion_fuente(fuente_id,id) ON DELETE RESTRICT,
      FOREIGN KEY(fuente_id,version_id) REFERENCES version_fuente(fuente_id,id) ON DELETE RESTRICT)''')
    op.execute('CREATE INDEX ix_recepcion_version_version ON recepcion_version_lista(version_id)')
    op.execute('''CREATE TABLE control_importacion_version (
      version_id uuid PRIMARY KEY REFERENCES version_fuente(id) ON DELETE RESTRICT,
      intento_id uuid NOT NULL REFERENCES intento_importacion(id) ON DELETE RESTRICT,
      numero_control integer NOT NULL, reclamaciones integer NOT NULL,
      revision_datos integer NOT NULL, ordinal_confirmado integer NOT NULL, segundos_consumidos double precision NOT NULL,
      ultima_actividad timestamptz NOT NULL, concesion_hasta timestamptz,
      CONSTRAINT ck_control_importacion CHECK(numero_control>=1 AND reclamaciones BETWEEN 1 AND 3
        AND ordinal_confirmado>=0 AND segundos_consumidos>=0))''')
    op.execute('CREATE INDEX ix_control_importacion_concesion ON control_importacion_version(concesion_hasta)')
    op.execute('''CREATE TABLE lote_importacion_lista (
      id uuid PRIMARY KEY, creado_en timestamptz NOT NULL,
      version_id uuid NOT NULL REFERENCES control_importacion_version(version_id) ON DELETE RESTRICT,
      intento_id uuid NOT NULL REFERENCES intento_importacion(id) ON DELETE RESTRICT,
      numero_control integer NOT NULL, desde integer NOT NULL, hasta integer NOT NULL, huella varchar(64) NOT NULL,
      CONSTRAINT uq_lote_importacion_desde UNIQUE(version_id,desde),
      CONSTRAINT ck_lote_importacion CHECK(desde>0 AND hasta>=desde AND numero_control>0 AND length(huella)=64))''')
    op.execute('CREATE INDEX ix_lote_importacion_version ON lote_importacion_lista(version_id)')
    for tabla in ('recepcion_version_lista', 'lote_importacion_lista'):
        op.execute(f'CREATE TRIGGER conservar_{tabla} BEFORE UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_inmutable()')
    op.execute('''CREATE FUNCTION listas_exigir_escritor(identificador uuid) RETURNS void LANGUAGE plpgsql AS $$
    DECLARE c control_importacion_version;
    BEGIN
      SELECT * INTO c FROM control_importacion_version WHERE version_id=identificador FOR UPDATE;
      IF NOT FOUND THEN RETURN; END IF;
      IF c.concesion_hasta IS NULL OR c.concesion_hasta<=clock_timestamp()
        OR c.intento_id::text IS DISTINCT FROM current_setting('listas.intento',true)
        OR c.numero_control::text IS DISTINCT FROM current_setting('listas.control',true)
        OR NOT EXISTS(SELECT 1 FROM intento_importacion WHERE id=c.intento_id AND version_id=identificador AND estado='EN_CURSO') THEN
        RAISE EXCEPTION 'Escritor de importación no vigente'; END IF;
    END $$''')
    op.execute('''CREATE FUNCTION listas_proteger_escritura_importacion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE identificador uuid; anterior uuid;
    BEGIN
      IF TG_TABLE_NAME IN ('registro_lista','relacion_registro') THEN
        IF TG_OP<>'DELETE' THEN identificador=NEW.version_id; END IF;
        IF TG_OP<>'INSERT' THEN anterior=OLD.version_id; END IF;
      ELSE
        IF TG_OP<>'DELETE' THEN SELECT version_id INTO identificador FROM registro_lista WHERE id=NEW.registro_id; END IF;
        IF TG_OP<>'INSERT' THEN SELECT version_id INTO anterior FROM registro_lista WHERE id=OLD.registro_id; END IF;
      END IF;
      PERFORM listas_exigir_escritor(identificador);
      UPDATE control_importacion_version SET revision_datos=revision_datos+1 WHERE version_id=identificador;
      IF anterior IS DISTINCT FROM identificador THEN
        PERFORM listas_exigir_escritor(anterior);
        UPDATE control_importacion_version SET revision_datos=revision_datos+1 WHERE version_id=anterior;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$''')
    for tabla in ('registro_lista', 'nombre_registro', 'identificador_registro', 'direccion_registro', 'atributo_registro', 'relacion_registro'):
        op.execute(f'CREATE TRIGGER exigir_escritor_importacion BEFORE INSERT OR UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_proteger_escritura_importacion()')
    op.execute('''CREATE FUNCTION listas_comprobar_lote() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE c control_importacion_version;
    BEGIN
      PERFORM listas_exigir_escritor(NEW.version_id);
      SELECT * INTO c FROM control_importacion_version WHERE version_id=NEW.version_id;
      IF NEW.intento_id<>c.intento_id OR NEW.numero_control<>c.numero_control OR NEW.desde<>c.ordinal_confirmado+1
        OR NEW.hasta<>(SELECT count(*) FROM registro_lista WHERE version_id=NEW.version_id) THEN
        RAISE EXCEPTION 'Lote discontinuo o de otro escritor'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER comprobar_lote BEFORE INSERT ON lote_importacion_lista FOR EACH ROW EXECUTE FUNCTION listas_comprobar_lote()')
    op.execute('''CREATE FUNCTION listas_comprobar_avance() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE identificador uuid; ordinal integer;
    BEGIN
      identificador=NEW.version_id;
      SELECT ordinal_confirmado INTO ordinal FROM control_importacion_version WHERE version_id=identificador;
      IF ordinal<>COALESCE((SELECT max(hasta) FROM lote_importacion_lista WHERE version_id=identificador),0)
        OR ordinal<>(SELECT count(*) FROM registro_lista WHERE version_id=identificador) THEN
        RAISE EXCEPTION 'Avance y lotes no coinciden'; END IF;
      RETURN NULL;
    END $$''')
    for tabla in ('control_importacion_version', 'lote_importacion_lista'):
        op.execute(f'CREATE CONSTRAINT TRIGGER comprobar_avance AFTER INSERT OR UPDATE ON {tabla} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_avance()')
    op.execute('''CREATE FUNCTION listas_comprobar_vinculo_importacion() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM intento_importacion WHERE id=NEW.intento_id AND recepcion_id=NEW.recepcion_id AND version_id=NEW.version_id)
        OR (NEW.intento_previo_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM intento_importacion WHERE id=NEW.intento_previo_id AND version_id=NEW.version_id AND estado='FALLIDO')) THEN
        RAISE EXCEPTION 'Vínculo de importación incompatible'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER comprobar_vinculo_importacion BEFORE INSERT ON recepcion_version_lista FOR EACH ROW EXECUTE FUNCTION listas_comprobar_vinculo_importacion()')
    op.execute('''CREATE FUNCTION listas_controlar_importacion() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'El control no se elimina'; END IF;
      IF TG_OP='UPDATE' AND (NEW.version_id<>OLD.version_id OR NEW.numero_control<OLD.numero_control
        OR NEW.ordinal_confirmado<OLD.ordinal_confirmado OR NEW.reclamaciones<OLD.reclamaciones
        OR NEW.revision_datos<OLD.revision_datos
        OR NEW.segundos_consumidos<OLD.segundos_consumidos) THEN RAISE EXCEPTION 'Control regresivo'; END IF;
      IF NOT EXISTS(SELECT 1 FROM recepcion_version_lista WHERE intento_id=NEW.intento_id AND version_id=NEW.version_id) THEN
        RAISE EXCEPTION 'Escritor sin vínculo'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER controlar_importacion BEFORE INSERT OR UPDATE OR DELETE ON control_importacion_version FOR EACH ROW EXECUTE FUNCTION listas_controlar_importacion()')
    op.execute('''CREATE FUNCTION listas_proteger_intento_importado() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM recepcion_version_lista WHERE intento_id=OLD.id) THEN
        IF TG_OP='DELETE' OR OLD.estado IN ('COMPLETADO','FALLIDO') THEN RAISE EXCEPTION 'Intento terminal inmutable'; END IF;
        IF (NEW.recepcion_id,NEW.version_id,NEW.informe) IS DISTINCT FROM (OLD.recepcion_id,OLD.version_id,OLD.informe) THEN
          RAISE EXCEPTION 'Origen de intento inmutable'; END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER proteger_intento_importado BEFORE UPDATE OR DELETE ON intento_importacion FOR EACH ROW EXECUTE FUNCTION listas_proteger_intento_importado()')
    op.execute('''CREATE FUNCTION listas_exigir_sellado_completo() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE c control_importacion_version; esperado integer;
    BEGIN
      SELECT * INTO c FROM control_importacion_version WHERE version_id=NEW.id;
      IF NOT FOUND THEN
        IF NEW.estado='VALIDA' AND NEW.version_importador='sintetico-v1' THEN RAISE EXCEPTION 'Falta control de importación'; END IF;
        RETURN NEW;
      END IF;
      IF (NEW.fuente_id,NEW.recepcion_id,NEW.esquema_id,NEW.archivo_raiz_id,NEW.archivo_contenido_id,
          NEW.formato,NEW.version_importador,NEW.version_normalizador,NEW.huella_contenido,NEW.generacion)
        IS DISTINCT FROM (OLD.fuente_id,OLD.recepcion_id,OLD.esquema_id,OLD.archivo_raiz_id,OLD.archivo_contenido_id,
          OLD.formato,OLD.version_importador,OLD.version_normalizador,OLD.huella_contenido,OLD.generacion) THEN
        RAISE EXCEPTION 'Origen de versión importada inmutable'; END IF;
      IF NEW.estado<>'VALIDA' THEN RETURN NEW; END IF;
      PERFORM listas_exigir_escritor(NEW.id);
      SELECT (detalle->>'registros')::integer INTO esperado FROM evento_recepcion_lista
        WHERE recepcion_id=NEW.recepcion_id AND tipo='VALIDACION_FINALIZADA' AND detalle->>'resultado'='VALIDO';
      IF esperado IS NULL OR esperado<>NEW.cantidad_registros OR c.ordinal_confirmado<>esperado
        OR EXISTS(SELECT 1 FROM relacion_registro WHERE version_id=NEW.id AND ambito_destino='INTERNO' AND registro_destino_id IS NULL)
        OR NOT EXISTS(SELECT 1 FROM intento_importacion WHERE id=c.intento_id AND fase='SELLADO') THEN
        RAISE EXCEPTION 'Importación incompleta para sellado'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER exigir_sellado_completo BEFORE UPDATE ON version_fuente FOR EACH ROW EXECUTE FUNCTION listas_exigir_sellado_completo()')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM recepcion_version_lista)')).scalar():
        raise RuntimeError('No se revierte importación con historial')
    op.execute('DROP TRIGGER exigir_sellado_completo ON version_fuente')
    op.execute('DROP TRIGGER proteger_intento_importado ON intento_importacion')
    for tabla in ('registro_lista', 'nombre_registro', 'identificador_registro', 'direccion_registro', 'atributo_registro', 'relacion_registro'):
        op.execute(f'DROP TRIGGER exigir_escritor_importacion ON {tabla}')
    for tabla in ('lote_importacion_lista','control_importacion_version','recepcion_version_lista'):
        op.drop_table(tabla)
    for funcion in ('listas_comprobar_lote','listas_comprobar_avance','listas_comprobar_vinculo_importacion',
                    'listas_controlar_importacion','listas_proteger_intento_importado','listas_exigir_sellado_completo',
                    'listas_proteger_escritura_importacion'):
        op.execute(f'DROP FUNCTION {funcion}()')
    op.execute('DROP FUNCTION listas_exigir_escritor(uuid)')
