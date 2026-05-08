# -*- coding: utf-8 -*-
"""station_prospective_place_ges/gaes: порядок отображения (display_order).

Revision ID: p1q2r3s4t5u6
Revises: c6d7e8f9a0b1
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

revision = "p1q2r3s4t5u6"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_GES = "station_prospective_place_ges"
TABLE_GAES = "station_prospective_place_gaes"


def upgrade():
    conn = op.get_bind()
    table_ges = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    table_gaes = column_utils.station_prospective_place_gaes_table_name(conn, SCHEMA_GEN)
    if table_ges is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table_ges, "display_order"):
        op.add_column(
            table_ges,
            sa.Column("display_order", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
    if table_gaes is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table_gaes, "display_order"):
        op.add_column(
            table_gaes,
            sa.Column("display_order", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table_ges = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    table_gaes = column_utils.station_prospective_place_gaes_table_name(conn, SCHEMA_GEN)
    if table_gaes is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table_gaes, "display_order"):
        op.drop_column(table_gaes, "display_order", schema=SCHEMA_GEN)
    if table_ges is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table_ges, "display_order"):
        op.drop_column(table_ges, "display_order", schema=SCHEMA_GEN)
