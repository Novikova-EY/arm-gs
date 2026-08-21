# -*- coding: utf-8 -*-
"""Добавить is_commissioning_q4 для агрегатов (gs_gen_machines).

Revision ID: b2c3d4e5f6a9
Revises: a1r2c3h4i5v6
Create Date: 2026-08-07
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "b2c3d4e5f6a9"
down_revision = "a1r2c3h4i5v6"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "gs_gen_machines"
COLUMN = "is_commissioning_q4"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        op.add_column(
            TABLE,
            sa.Column(
                COLUMN,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN, schema=SCHEMA)
