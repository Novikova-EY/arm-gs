# -*- coding: utf-8 -*-
"""gs_gen_stations: признак электростанции (station_sign).

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-06-09
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "w7x8y9z0a1b2"
down_revision = "v6w7x8y9z0a1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "gs_gen_stations"
COLUMN = "station_sign"


def upgrade():
    conn = op.get_bind()
    table = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)
    if table is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table, COLUMN):
        op.add_column(
            table,
            sa.Column(COLUMN, sa.String(length=20), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)
    if table is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table, COLUMN):
        op.drop_column(table, COLUMN, schema=SCHEMA_GEN)
