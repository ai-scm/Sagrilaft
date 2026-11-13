"""Reserva atómica de grupos de consultas, sin modificar el historial anterior."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b32c45d67e89"
down_revision = "a21b34c56d78"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("grupo_consulta_lista",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_emisor", sa.String(500), nullable=False),
        sa.Column("actor_sujeto", sa.String(200), nullable=False),
        sa.Column("expediente_id", sa.String(), sa.ForeignKey("formularios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("clave", sa.String(128), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("respuesta", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("actor_emisor", "actor_sujeto", "expediente_id", "clave", name="uq_grupo_listas_peticion"),
        sa.UniqueConstraint("id", "actor_emisor", "actor_sujeto", "expediente_id", name="uq_grupo_listas_contexto"))
    op.create_foreign_key("fk_consulta_grupo", "consulta_lista", "grupo_consulta_lista", ["grupo_id", "actor_emisor", "actor_sujeto", "expediente_id"], ["id", "actor_emisor", "actor_sujeto", "expediente_id"], ondelete="RESTRICT", deferrable=True, initially="IMMEDIATE")
    op.create_check_constraint("ck_grupo_con_expediente", "consulta_lista", "grupo_id IS NULL OR expediente_id IS NOT NULL")
    op.execute("CREATE TRIGGER conservar_grupo BEFORE UPDATE OR DELETE ON grupo_consulta_lista FOR EACH ROW EXECUTE FUNCTION listas_inmutable()")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM grupo_consulta_lista)")).scalar():
        raise RuntimeError("No se revierte el esquema con grupos: preservar el historial")
    op.drop_constraint("ck_grupo_con_expediente", "consulta_lista", type_="check")
    op.drop_constraint("fk_consulta_grupo", "consulta_lista", type_="foreignkey")
    op.drop_table("grupo_consulta_lista")
