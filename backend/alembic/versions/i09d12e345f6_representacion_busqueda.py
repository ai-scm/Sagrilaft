"""Generaciones de búsqueda independientes, completas e inmutables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "i09d12e345f6"
down_revision = "h98c01d234e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("generacion_busqueda_lista",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("version_fuente.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("adaptador_version", sa.String(64), nullable=False),
        sa.Column("normalizacion_version", sa.String(64), nullable=False),
        sa.Column("catalogo_huella", sa.String(64), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("cantidad_registros", sa.Integer(), nullable=False),
        sa.Column("cantidad_consultables", sa.Integer(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.UniqueConstraint("version_id", "id", name="uq_generacion_version"),
        sa.UniqueConstraint("version_id", "adaptador_version", "normalizacion_version", "catalogo_huella", name="uq_generacion_receta"),
        sa.CheckConstraint("estado IN ('PREPARANDO','LISTA')", name="ck_generacion_estado"),
        sa.CheckConstraint("cantidad_registros > 0 AND cantidad_consultables BETWEEN 0 AND cantidad_registros", name="ck_generacion_conteos"),
        sa.CheckConstraint("length(huella)=64 AND length(catalogo_huella)=64", name="ck_generacion_huellas"))
    op.create_table("registro_busqueda_lista",
        sa.Column("generacion_id", sa.Uuid(), primary_key=True),
        sa.Column("registro_id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("datos", JSONB(), nullable=True),
        sa.Column("motivo_exclusion", sa.String(64), nullable=True),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["version_id", "generacion_id"], ["generacion_busqueda_lista.version_id", "generacion_busqueda_lista.id"], ondelete="RESTRICT", name="fk_busqueda_generacion_version"),
        sa.ForeignKeyConstraint(["version_id", "registro_id"], ["registro_lista.version_id", "registro_lista.id"], ondelete="RESTRICT", name="fk_busqueda_registro_version"),
        sa.CheckConstraint("(datos IS NOT NULL AND motivo_exclusion IS NULL) OR (datos IS NULL AND motivo_exclusion IS NOT NULL)", name="ck_busqueda_exclusion"),
        sa.CheckConstraint("length(huella)=64", name="ck_busqueda_huella"))
    op.create_table("termino_busqueda_lista",
        sa.Column("generacion_id", sa.Uuid(), primary_key=True),
        sa.Column("registro_id", sa.Uuid(), primary_key=True),
        sa.Column("clase", sa.String(20), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("huella_valor", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["generacion_id", "registro_id"], ["registro_busqueda_lista.generacion_id", "registro_busqueda_lista.registro_id"], ondelete="RESTRICT", name="fk_termino_registro"),
        sa.CheckConstraint("clase IN ('NOMBRE','IDENTIFICADOR') AND ordinal >= 0 AND length(huella_valor)=64", name="ck_termino_busqueda"))
    op.create_index("ix_termino_generacion_valor", "termino_busqueda_lista", ["generacion_id", "clase", "huella_valor"])
    op.execute("""CREATE FUNCTION listas_proteger_generacion() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR (TG_OP='UPDATE' AND OLD.estado='LISTA') THEN
        RAISE EXCEPTION 'Generación de búsqueda inmutable';
      END IF;
      IF TG_OP='INSERT' AND NEW.estado<>'PREPARANDO' THEN
        RAISE EXCEPTION 'La generación debe prepararse';
      END IF;
      PERFORM 1 FROM version_fuente WHERE id=NEW.version_id AND estado='VALIDA' FOR SHARE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Versión de búsqueda no válida'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE FUNCTION listas_proteger_derivados() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Derivado de búsqueda inmutable'; END IF;
      PERFORM 1 FROM generacion_busqueda_lista WHERE id=NEW.generacion_id AND estado='PREPARANDO' FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Generación cerrada o inexistente'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE FUNCTION listas_comprobar_generacion() RETURNS trigger LANGUAGE plpgsql AS $$
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
    op.execute("CREATE TRIGGER proteger_generacion BEFORE INSERT OR UPDATE OR DELETE ON generacion_busqueda_lista FOR EACH ROW EXECUTE FUNCTION listas_proteger_generacion()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_generacion AFTER INSERT ON generacion_busqueda_lista DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_generacion()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_sello_generacion AFTER UPDATE ON generacion_busqueda_lista DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (OLD.estado IS DISTINCT FROM NEW.estado) EXECUTE FUNCTION listas_comprobar_generacion()")
    for tabla in ("registro_busqueda_lista", "termino_busqueda_lista"):
        op.execute(f"CREATE TRIGGER proteger_derivado BEFORE INSERT OR UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_proteger_derivados()")


def downgrade():
    for tabla in ("termino_busqueda_lista", "registro_busqueda_lista", "generacion_busqueda_lista"):
        op.drop_table(tabla)
    for funcion in ("listas_comprobar_generacion", "listas_proteger_derivados", "listas_proteger_generacion"):
        op.execute(f"DROP FUNCTION {funcion}()")
