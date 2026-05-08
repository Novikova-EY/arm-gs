# -*- coding: utf-8 -*-
"""ges_tep_source_project_indicators: стоимость (капзатраты без ПИР) и годы (Year).

Revision ID: y0z1a2b3c4d5
Revises: x9a0b1c2d3e4
Create Date: 2026-04-13
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "y0z1a2b3c4d5"
down_revision = "x9a0b1c2d3e4"
branch_labels = None
depends_on = None

TABLE = "ges_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"


def upgrade():
    conn = op.get_bind()
    table = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table is None or table_years is None:
        return
    for col, coltype in (
        ("capital_cost_wo_pir_total_million_rub", sa.Numeric(24, 4)),
        ("id_year_capital_cost_wo_pir_total", sa.Integer()),
        ("capital_cost_wo_pir_ges_with_reservoir_million_rub", sa.Numeric(24, 4)),
        ("id_year_capital_cost_wo_pir_ges_with_reservoir", sa.Integer()),
        ("capital_cost_wo_pir_svm_million_rub", sa.Numeric(24, 4)),
        ("id_year_capital_cost_wo_pir_svm", sa.Integer()),
    ):
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.add_column(table, sa.Column(col, coltype, nullable=True), schema=SCHEMA_GEN)

    for fk_name, col in (
        ("fk_ges_tep_cap_cost_total_year", "id_year_capital_cost_wo_pir_total"),
        ("fk_ges_tep_cap_cost_ges_year", "id_year_capital_cost_wo_pir_ges_with_reservoir"),
        ("fk_ges_tep_cap_cost_svm_year", "id_year_capital_cost_wo_pir_svm"),
    ):
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, fk_name):
            op.create_foreign_key(
                fk_name,
                table,
                table_years,
                [col],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )

    for ix_name, col in (
        ("ix_ges_tep_cap_cost_total_year", "id_year_capital_cost_wo_pir_total"),
        ("ix_ges_tep_cap_cost_ges_year", "id_year_capital_cost_wo_pir_ges_with_reservoir"),
        ("ix_ges_tep_cap_cost_svm_year", "id_year_capital_cost_wo_pir_svm"),
    ):
        if not column_utils.index_exists(conn, SCHEMA_GEN, ix_name):
            op.create_index(ix_name, table, [col], unique=False, schema=SCHEMA_GEN)


def downgrade():
    op.drop_index("ix_ges_tep_cap_cost_svm_year", table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_index("ix_ges_tep_cap_cost_ges_year", table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_index("ix_ges_tep_cap_cost_total_year", table_name=TABLE, schema=SCHEMA_GEN)

    op.drop_constraint("fk_ges_tep_cap_cost_svm_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_ges_tep_cap_cost_ges_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_ges_tep_cap_cost_total_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")

    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_svm", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_svm_million_rub", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_ges_with_reservoir", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_ges_with_reservoir_million_rub", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_total", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_total_million_rub", schema=SCHEMA_GEN)
