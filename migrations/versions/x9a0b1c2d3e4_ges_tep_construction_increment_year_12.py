# -*- coding: utf-8 -*-
"""ges_tep_source_project_indicators: прирост мощности за 12-й год.

Revision ID: x9a0b1c2d3e4
Revises: w6x7y8z9a0b1
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


revision = "x9a0b1c2d3e4"
down_revision = "w6x7y8z9a0b1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "ges_tep_source_project_indicators"


def upgrade():
    conn = op.get_bind()
    table = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table, "construction_increment_year_12_mw"):
        op.add_column(
            table,
            sa.Column("construction_increment_year_12_mw", sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table, "construction_increment_year_12_mw"):
        op.drop_column(table, "construction_increment_year_12_mw", schema=SCHEMA_GEN)
