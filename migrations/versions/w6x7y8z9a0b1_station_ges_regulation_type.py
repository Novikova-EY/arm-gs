# -*- coding: utf-8 -*-
"""station_prospective_place_ges: поле regulation_type (вид регулирования).

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
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


revision = "w6x7y8z9a0b1"
down_revision = "v5w6x7y8z9a0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_ges"


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    if table is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table, "regulation_type"):
        op.add_column(
            table,
            sa.Column("regulation_type", sa.String(length=500), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    if table is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table, "regulation_type"):
        op.drop_column(table, "regulation_type", schema=SCHEMA_GEN)
