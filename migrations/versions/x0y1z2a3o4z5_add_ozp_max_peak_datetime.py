# -*- coding: utf-8 -*-
"""Строка даты/времени максимума ОЗП (дд.мм чч:мм) в gs_pd_ozp_max_power_params.

Revision ID: x0y1z2a3o4z5
Revises: w9x0y1z2a3b4
Create Date: 2026-09-08
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

revision = "x0y1z2a3o4z5"
down_revision = "w9x0y1z2a3b4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_ozp_max_power_params"
COL = "peak_datetime"
COL_COMMENT = (
    "Дата и время прохождения максимума потребления мощности, дд.мм чч:мм"
)


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_PD, TABLE):
        return
    if not column_utils.table_has_column(conn, SCHEMA_PD, TABLE, COL):
        op.add_column(
            TABLE,
            sa.Column(COL, sa.String(length=64), nullable=True),
            schema=SCHEMA_PD,
        )
    conn.execute(
        text(f'COMMENT ON COLUMN "{SCHEMA_PD}"."{TABLE}"."{COL}" IS :comment'),
        {"comment": COL_COMMENT},
    )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_PD, TABLE):
        return
    if column_utils.table_has_column(conn, SCHEMA_PD, TABLE, COL):
        op.drop_column(TABLE, COL, schema=SCHEMA_PD)
