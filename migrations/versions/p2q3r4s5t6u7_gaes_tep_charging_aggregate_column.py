# -*- coding: utf-8 -*-
"""gaes_tep_source: годовое потребление на заряд без разбивки по очередям.

Revision ID: p2q3r4s5t6u7
Revises: n5o6p7q8r9s0
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

revision = "p2q3r4s5t6u7"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
COL = "annual_charging_electricity_consumption_million_kwh"


def upgrade():
    conn = op.get_bind()
    table = column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, COL):
        op.add_column(
            table,
            sa.Column(COL, sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, COL):
        op.drop_column(table, COL, schema=SCHEMA_GEN)
