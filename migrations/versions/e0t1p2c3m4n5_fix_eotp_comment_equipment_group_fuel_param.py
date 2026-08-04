# -*- coding: utf-8 -*-
"""Обновить комментарий eotp в gs_fue_equipment_group_fuel_param.

Revision ID: e0t1p2c3m4n5
Revises: o8p9q0r1s2t3
Create Date: 2026-08-04
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "e0t1p2c3m4n5"
down_revision = "o8p9q0r1s2t3"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_fuel_param"
COMMENT = "Отпуск ЭЭ, тыс.кВтч"
OLD_COMMENT = "Отпуск"
COLUMN = "eotp"


def _comment_on_column(conn, column: str, comment: str | None) -> None:
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, column):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{SCHEMA}"."{TABLE}"."{column}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    conn = op.get_bind()
    _comment_on_column(conn, COLUMN, COMMENT)


def downgrade():
    conn = op.get_bind()
    _comment_on_column(conn, COLUMN, OLD_COMMENT)
