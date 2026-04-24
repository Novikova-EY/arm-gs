# -*- coding: utf-8 -*-
"""gaes_tep_source_project_indicators: 12-й год прироста мощности и капзатраты без ПИР (как у ГЭС).

Revision ID: h1i2j3k4l5m6
Revises: g2h3i4j5k6l7
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "h1i2j3k4l5m6"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None

TABLE = "gaes_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("construction_increment_year_12_mw", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("capital_cost_wo_pir_total_million_rub", sa.Numeric(24, 4), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("id_year_capital_cost_wo_pir_total", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "capital_cost_wo_pir_ges_with_reservoir_million_rub",
            sa.Numeric(24, 4),
            nullable=True,
        ),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("id_year_capital_cost_wo_pir_ges_with_reservoir", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("capital_cost_wo_pir_svm_million_rub", sa.Numeric(24, 4), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("id_year_capital_cost_wo_pir_svm", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )

    op.create_foreign_key(
        "fk_gaes_tep_cap_cost_total_year",
        TABLE,
        "gs_years",
        ["id_year_capital_cost_wo_pir_total"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_gaes_tep_cap_cost_ges_year",
        TABLE,
        "gs_years",
        ["id_year_capital_cost_wo_pir_ges_with_reservoir"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_gaes_tep_cap_cost_svm_year",
        TABLE,
        "gs_years",
        ["id_year_capital_cost_wo_pir_svm"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_gaes_tep_cap_cost_total_year",
        TABLE,
        ["id_year_capital_cost_wo_pir_total"],
        unique=False,
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_gaes_tep_cap_cost_ges_year",
        TABLE,
        ["id_year_capital_cost_wo_pir_ges_with_reservoir"],
        unique=False,
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_gaes_tep_cap_cost_svm_year",
        TABLE,
        ["id_year_capital_cost_wo_pir_svm"],
        unique=False,
        schema=SCHEMA_GEN,
    )


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
