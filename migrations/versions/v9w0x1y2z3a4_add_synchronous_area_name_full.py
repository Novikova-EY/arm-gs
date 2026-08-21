# -*- coding: utf-8 -*-
"""Добавить name_full (полное наименование) в gs_sys_synchronous_areas.

Revision ID: v9w0x1y2z3a4
Revises: u8v9w0x1y2z3
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

revision = "v9w0x1y2z3a4"
down_revision = "u8v9w0x1y2z3"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
TABLE = "gs_sys_synchronous_areas"
COLUMN = "name_full"
INDEX = "ix_gs_sys_synchronous_areas_name_full"


def upgrade():
    conn = op.get_bind()
    table = column_utils.refdata_table_name(conn, SCHEMA, TABLE) or TABLE
    if not column_utils.table_exists(conn, SCHEMA, table):
        return
    if not column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
        op.add_column(
            table,
            sa.Column(COLUMN, sa.String(256), nullable=True),
            schema=SCHEMA,
        )
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA}.{table}
            SET {COLUMN} = name
            WHERE coalesce({COLUMN}, '') = ''
              AND coalesce(name, '') <> ''
            """
        )
    )
    if not column_utils.index_exists(conn, SCHEMA, INDEX):
        op.create_index(INDEX, table, [COLUMN], unique=False, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    table = column_utils.refdata_table_name(conn, SCHEMA, TABLE) or TABLE
    if not column_utils.table_exists(conn, SCHEMA, table):
        return
    if column_utils.index_exists(conn, SCHEMA, INDEX):
        op.drop_index(INDEX, table_name=table, schema=SCHEMA)
    if column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
        op.drop_column(table, COLUMN, schema=SCHEMA)
