# -*- coding: utf-8 -*-
"""Колонка parent_key для двухуровневых строк перетоков баланса мощности.

Revision ID: x1y2z3a4b5c6
Revises: w0x1y2z3a4b5
Create Date: 2026-08-19
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "x1y2z3a4b5c6"
down_revision = "w0x1y2z3a4b5"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
TABLE = "gs_bem_power_balance_custom_flow_rows"
COLUMN = "parent_key"
INDEX = "ix_gs_bem_pb_cfr_parent_key"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.String(length=128), nullable=True),
            schema=SCHEMA,
        )
        op.execute(
            sa.text(
                f'UPDATE "{SCHEMA}"."{TABLE}" '
                f"SET {COLUMN} = direction "
                f"WHERE {COLUMN} IS NULL OR {COLUMN} = ''"
            )
        )
    if not column_utils.index_exists(conn, SCHEMA, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=False, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if column_utils.index_exists(conn, SCHEMA, INDEX):
        op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA)
    if column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN, schema=SCHEMA)
