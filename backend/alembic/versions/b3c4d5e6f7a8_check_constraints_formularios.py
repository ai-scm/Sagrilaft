"""check_constraints_formularios

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-08

Agrega restricciones CHECK de bajo riesgo para valores que ya valida la
aplicacion: DV, fecha legal de firma y porcentajes de participacion/control.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_formularios_digito_verificacion_formato",
        "formularios",
        "digito_verificacion IS NULL OR digito_verificacion IN ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'NA')",
    )
    op.create_check_constraint(
        "ck_formularios_dia_firma_rango",
        "formularios",
        "dia_firma IS NULL OR dia_firma BETWEEN 1 AND 31",
    )
    op.create_check_constraint(
        "ck_formularios_mes_firma_rango",
        "formularios",
        "mes_firma IS NULL OR mes_firma BETWEEN 1 AND 12",
    )
    op.create_check_constraint(
        "ck_formularios_year_firma_rango",
        "formularios",
        "year_firma IS NULL OR year_firma BETWEEN 2000 AND 2100",
    )
    op.create_check_constraint(
        "ck_formulario_accionistas_porcentaje_rango",
        "formulario_accionistas",
        "porcentaje IS NULL OR porcentaje BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_formulario_beneficiarios_finales_porcentaje_rango",
        "formulario_beneficiarios_finales",
        "porcentaje IS NULL OR porcentaje BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_formulario_beneficiarios_finales_porcentaje_rango",
        "formulario_beneficiarios_finales",
        type_="check",
    )
    op.drop_constraint(
        "ck_formulario_accionistas_porcentaje_rango",
        "formulario_accionistas",
        type_="check",
    )
    op.drop_constraint("ck_formularios_year_firma_rango", "formularios", type_="check")
    op.drop_constraint("ck_formularios_mes_firma_rango", "formularios", type_="check")
    op.drop_constraint("ck_formularios_dia_firma_rango", "formularios", type_="check")
    op.drop_constraint("ck_formularios_digito_verificacion_formato", "formularios", type_="check")
