# -*- coding: utf-8 -*-
"""gaes_tep_source_project_indicators: 12-й год прироста мощности и капзатраты без ПИР (как у ГЭС).

Revision ID: h1i2j3k4l5m6
Revises: g2h3i4j5k6l7
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


revision = "h1i2j3k4l5m6"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None

TABLE = "gaes_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"


def upgrade():
    conn = op.get_bind()
    table = column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table is None or table_years is None:
        return

    cols = (
        ("construction_increment_year_12_mw", sa.Column("construction_increment_year_12_mw", sa.String(length=100), nullable=True)),
        ("capital_cost_wo_pir_total_million_rub", sa.Column("capital_cost_wo_pir_total_million_rub", sa.Numeric(24, 4), nullable=True)),
        ("id_year_capital_cost_wo_pir_total", sa.Column("id_year_capital_cost_wo_pir_total", sa.Integer(), nullable=True)),
        (
            "capital_cost_wo_pir_ges_with_reservoir_million_rub",
            sa.Column(
                "capital_cost_wo_pir_ges_with_reservoir_million_rub",
                sa.Numeric(24, 4),
                nullable=True,
            ),
        ),
        (
            "id_year_capital_cost_wo_pir_ges_with_reservoir",
            sa.Column("id_year_capital_cost_wo_pir_ges_with_reservoir", sa.Integer(), nullable=True),
        ),
        ("capital_cost_wo_pir_svm_million_rub", sa.Column("capital_cost_wo_pir_svm_million_rub", sa.Numeric(24, 4), nullable=True)),
        ("id_year_capital_cost_wo_pir_svm", sa.Column("id_year_capital_cost_wo_pir_svm", sa.Integer(), nullable=True)),
    )
    for name, col in cols:
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, name):
            op.add_column(table, col, schema=SCHEMA_GEN)

    fks = (
        (
            "fk_gaes_tep_cap_cost_total_year",
            ["id_year_capital_cost_wo_pir_total"],
        ),
        (
            "fk_gaes_tep_cap_cost_ges_year",
            ["id_year_capital_cost_wo_pir_ges_with_reservoir"],
        ),
        (
            "fk_gaes_tep_cap_cost_svm_year",
            ["id_year_capital_cost_wo_pir_svm"],
        ),
    )
    for fk_name, local_cols in fks:
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, fk_name):
            op.create_foreign_key(
                fk_name,
                table,
                table_years,
                local_cols,
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )

    indexes = (
        ("ix_gaes_tep_cap_cost_total_year", ["id_year_capital_cost_wo_pir_total"]),
        ("ix_gaes_tep_cap_cost_ges_year", ["id_year_capital_cost_wo_pir_ges_with_reservoir"]),
        ("ix_gaes_tep_cap_cost_svm_year", ["id_year_capital_cost_wo_pir_svm"]),
    )
    for ix_name, ix_cols in indexes:
        if not column_utils.index_exists(conn, SCHEMA_GEN, ix_name):
            op.create_index(ix_name, table, ix_cols, unique=False, schema=SCHEMA_GEN)


def downgrade():
    op.drop_index("ix_gaes_tep_cap_cost_svm_year", table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_index("ix_gaes_tep_cap_cost_ges_year", table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_index("ix_gaes_tep_cap_cost_total_year", table_name=TABLE, schema=SCHEMA_GEN)

    op.drop_constraint("fk_gaes_tep_cap_cost_svm_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_gaes_tep_cap_cost_ges_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_gaes_tep_cap_cost_total_year", TABLE, schema=SCHEMA_GEN, type_="foreignkey")

    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_svm", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_svm_million_rub", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_ges_with_reservoir", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_ges_with_reservoir_million_rub", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "id_year_capital_cost_wo_pir_total", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "capital_cost_wo_pir_total_million_rub", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "construction_increment_year_12_mw", schema=SCHEMA_GEN)
