# -*- coding: utf-8 -*-
"""Добавить name_dat (дательный падеж) в gs_sys_energy_units.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a9
Create Date: 2026-08-10
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

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a9"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
TABLE = "gs_sys_energy_units"
COLUMN = "name_dat"


def upgrade():
    conn = op.get_bind()
    table = column_utils.refdata_table_name(conn, SCHEMA, TABLE) or TABLE
    if not column_utils.table_exists(conn, SCHEMA, table):
        return
    if not column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
        op.add_column(
            table,
            sa.Column(COLUMN, sa.String(255), nullable=False, server_default=""),
            schema=SCHEMA,
        )
    # Для Таймыра — краткий дательный для итогов «Итого по Таймыру»
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA}.{table}
            SET {COLUMN} = 'Таймыру'
            WHERE lower(coalesce(name, '')) LIKE '%%таймыр%%'
              AND (coalesce({COLUMN}, '') = '')
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    table = column_utils.refdata_table_name(conn, SCHEMA, TABLE) or TABLE
    if not column_utils.table_exists(conn, SCHEMA, table):
        return
    if column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
        op.drop_column(table, COLUMN, schema=SCHEMA)
