# -*- coding: utf-8 -*-
"""ГЭС/ГАЭС: срок строительства — numeric(12,1) вместо integer.

Revision ID: r3s4t5u6v7w8
Revises: p1q2r3s4t5u6
Create Date: 2026-04-22
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "r3s4t5u6v7w8"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"


def upgrade():
    conn = op.get_bind()
    for table, col in (
        (column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.station_prospective_place_gaes_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "construction_period_years"),
    ):
        if table is None:
            continue
        op.alter_column(
            table,
            col,
            type_=sa.Numeric(12, 1),
            schema=SCHEMA_GEN,
            postgresql_using=f"{col}::numeric(12,1)",
        )


def downgrade():
    conn = op.get_bind()
    for table, col in (
        (column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.station_prospective_place_gaes_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "construction_period_years"),
        (column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "construction_period_years"),
    ):
        if table is None:
            continue
        op.alter_column(
            table,
            col,
            type_=sa.Integer(),
            schema=SCHEMA_GEN,
            postgresql_using=f"round({col})::integer",
        )
