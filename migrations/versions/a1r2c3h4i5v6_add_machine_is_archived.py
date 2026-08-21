# -*- coding: utf-8 -*-
"""Добавить is_archived для агрегатов (gs_gen_machines).

Revision ID: a1r2c3h4i5v6
Revises: f1u2e3f4o5r6
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

revision = "a1r2c3h4i5v6"
down_revision = "f1u2e3f4o5r6"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "gs_gen_machines"
COLUMN = "is_archived"
IX_NAME = f"ix_{TABLE}_{COLUMN}"


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
    if not column_utils.index_exists(conn, SCHEMA, IX_NAME):
        op.create_index(IX_NAME, TABLE, [COLUMN], schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if column_utils.index_exists(conn, SCHEMA, IX_NAME):
        op.drop_index(IX_NAME, table_name=TABLE, schema=SCHEMA)
    if column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN, schema=SCHEMA)
