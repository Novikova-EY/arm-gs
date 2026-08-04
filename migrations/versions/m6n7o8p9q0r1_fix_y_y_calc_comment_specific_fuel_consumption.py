# -*- coding: utf-8 -*-
"""Обновить комментарии y / y_calc в gs_fue_equipment_group_specific_fuel_consumption.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
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

revision = "m6n7o8p9q0r1"
down_revision = "l5m6n7o8p9q0"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_specific_fuel_consumption"
COMMENT = "Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал"
OLD_COMMENT = "Удельная выработка эл.эн. на тепловом потреблении"
COLUMNS = ("y", "y_calc")


def _comment_on_column(conn, column: str, comment: str | None) -> None:
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, column):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{SCHEMA}"."{TABLE}"."{column}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    conn = op.get_bind()
    for column in COLUMNS:
        _comment_on_column(conn, column, COMMENT)


def downgrade():
    conn = op.get_bind()
    for column in COLUMNS:
        _comment_on_column(conn, column, OLD_COMMENT)
