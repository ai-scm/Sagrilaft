"""esquema_inicial

Revision ID: a5aed126c881
Revises:
Create Date: 2026-04-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a5aed126c881"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "formularios",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("codigo_peticion", sa.String(), nullable=True),
        sa.Column("estado", sa.String(), nullable=True),
        sa.Column("pagina_actual", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # Clasificación
        sa.Column("tipo_contraparte", sa.String(), nullable=True),
        sa.Column("tipo_persona", sa.String(), nullable=True),
        sa.Column("tipo_solicitud", sa.String(), nullable=True),
        sa.Column("clasificacion_actividad", sa.String(), nullable=True),
        # Información básica empresa
        sa.Column("razon_social", sa.String(), nullable=True),
        sa.Column("tipo_identificacion", sa.String(), nullable=True),
        sa.Column("numero_identificacion", sa.String(), nullable=True),
        sa.Column("digito_verificacion", sa.String(), nullable=True),
        sa.Column("direccion", sa.String(), nullable=True),
        sa.Column("pais", sa.String(), nullable=True),
        sa.Column("departamento", sa.String(), nullable=True),
        sa.Column("ciudad", sa.String(), nullable=True),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("fax", sa.String(), nullable=True),
        sa.Column("correo", sa.String(), nullable=True),
        sa.Column("codigo_ica", sa.String(), nullable=True),
        sa.Column("pagina_web", sa.String(), nullable=True),
        # Representante legal
        sa.Column("nombre_representante", sa.String(), nullable=True),
        sa.Column("tipo_doc_representante", sa.String(), nullable=True),
        sa.Column("numero_doc_representante", sa.String(), nullable=True),
        sa.Column("fecha_expedicion", sa.String(), nullable=True),
        sa.Column("ciudad_expedicion", sa.String(), nullable=True),
        sa.Column("nacionalidad", sa.String(), nullable=True),
        sa.Column("fecha_nacimiento", sa.String(), nullable=True),
        sa.Column("ciudad_nacimiento", sa.String(), nullable=True),
        sa.Column("profesion", sa.String(), nullable=True),
        sa.Column("correo_representante", sa.String(), nullable=True),
        sa.Column("telefono_representante", sa.String(), nullable=True),
        sa.Column("direccion_funciones", sa.String(), nullable=True),
        sa.Column("ciudad_funciones", sa.String(), nullable=True),
        sa.Column("direccion_residencia", sa.String(), nullable=True),
        sa.Column("ciudad_residencia", sa.String(), nullable=True),
        # Información financiera
        sa.Column("actividad_economica", sa.String(), nullable=True),
        sa.Column("codigo_ciiu", sa.String(), nullable=True),
        sa.Column("ingresos_mensuales", sa.Float(), nullable=True),
        sa.Column("otros_ingresos", sa.Float(), nullable=True),
        sa.Column("egresos_mensuales", sa.Float(), nullable=True),
        sa.Column("total_activos", sa.Float(), nullable=True),
        sa.Column("total_pasivos", sa.Float(), nullable=True),
        sa.Column("patrimonio", sa.Float(), nullable=True),
        # Operaciones en moneda extranjera
        sa.Column("realiza_operaciones_moneda_extranjera", sa.String(), nullable=True),
        sa.Column("paises_operaciones", sa.String(), nullable=True),
        sa.Column("tipos_transaccion", sa.Text(), nullable=True),
        sa.Column("tipos_transaccion_otros", sa.String(), nullable=True),
        # Clasificación empresa y régimen tributario
        sa.Column("actividad_clasificacion", sa.String(), nullable=True),
        sa.Column("actividad_especifica", sa.String(), nullable=True),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("superintendencia", sa.String(), nullable=True),
        sa.Column("responsabilidades_renta", sa.String(), nullable=True),
        sa.Column("autorretenedor", sa.String(), nullable=True),
        sa.Column("responsabilidades_iva", sa.String(), nullable=True),
        sa.Column("regimen_iva", sa.String(), nullable=True),
        sa.Column("gran_contribuyente", sa.String(), nullable=True),
        sa.Column("entidad_sin_animo_lucro", sa.String(), nullable=True),
        sa.Column("retencion_ica", sa.String(), nullable=True),
        sa.Column("impuesto_ica", sa.String(), nullable=True),
        sa.Column("entidad_oficial", sa.String(), nullable=True),
        sa.Column("exento_retencion_fuente", sa.String(), nullable=True),
        # Contactos
        sa.Column("contacto_ordenes_nombre", sa.String(), nullable=True),
        sa.Column("contacto_ordenes_cargo", sa.String(), nullable=True),
        sa.Column("contacto_ordenes_telefono", sa.String(), nullable=True),
        sa.Column("contacto_ordenes_correo", sa.String(), nullable=True),
        sa.Column("contacto_pagos_nombre", sa.String(), nullable=True),
        sa.Column("contacto_pagos_cargo", sa.String(), nullable=True),
        sa.Column("contacto_pagos_telefono", sa.String(), nullable=True),
        sa.Column("contacto_pagos_correo", sa.String(), nullable=True),
        # Autorizaciones
        sa.Column("autorizacion_datos", sa.Boolean(), nullable=True),
        sa.Column("declaracion_origen_fondos", sa.Boolean(), nullable=True),
        sa.Column("origen_fondos", sa.Text(), nullable=True),
        # Firma
        sa.Column("fecha_firma", sa.String(), nullable=True),
        sa.Column("ciudad_firma", sa.String(), nullable=True),
        sa.Column("nombre_firma", sa.String(), nullable=True),
        # Datos dinámicos (JSON serializado)
        sa.Column("junta_directiva", sa.Text(), nullable=True),
        sa.Column("accionistas", sa.Text(), nullable=True),
        sa.Column("beneficiario_final", sa.Text(), nullable=True),
        sa.Column("referencias_comerciales", sa.Text(), nullable=True),
        sa.Column("referencias_bancarias", sa.Text(), nullable=True),
        sa.Column("informacion_bancaria_pagos", sa.Text(), nullable=True),
        sa.Column("clasificaciones", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_peticion"),
    )

    op.create_table(
        "documentos_adjuntos",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("tipo_documento", sa.String(), nullable=False),
        sa.Column("nombre_archivo", sa.String(), nullable=False),
        sa.Column("ruta_archivo", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("tamano", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "resultados_validacion",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("campo", sa.String(), nullable=True),
        sa.Column("resultado", sa.String(), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("valor_formulario", sa.String(), nullable=True),
        sa.Column("valor_documento", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "accesos_manuales",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("pin_hash", sa.String(), nullable=False),
        sa.Column("token_diligenciamiento", sa.String(), nullable=False),
        sa.Column("correo_destinatario", sa.String(), nullable=False),
        sa.Column("razon_social", sa.String(), nullable=False),
        sa.Column("tipo_contraparte", sa.String(), nullable=False),
        sa.Column("area_responsable", sa.String(), nullable=False),
        sa.Column("formulario_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["formulario_id"], ["formularios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formulario_id"),
        sa.UniqueConstraint("token_diligenciamiento"),
    )


def downgrade() -> None:
    op.drop_table("accesos_manuales")
    op.drop_table("resultados_validacion")
    op.drop_table("documentos_adjuntos")
    op.drop_table("formularios")
