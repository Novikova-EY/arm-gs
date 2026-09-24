# -*- coding: utf-8 -*-
"""Источник характеристик топлива на листе «Справочник».

Revision ID: y1z2a3b4c5d6
Revises: x0y1z2a3o4z5
Create Date: 2026-09-10
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

revision = "y1z2a3b4c5d6"
down_revision = "x0y1z2a3o4z5"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
TABLE = "gs_eco_operating_tes_fuel_chars"
COL = "source_key"
COL_COMMENT = (
    "Источник характеристик топлива листа «Справочник»: "
    "thermal / method / industry / table21 / rosstat"
)


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        return
    if not column_utils.table_has_column(conn, SCHEMA_ECO, TABLE, COL):
        op.add_column(
            TABLE,
            sa.Column(COL, sa.String(length=40), nullable=True),
            schema=SCHEMA_ECO,
        )
    conn.execute(
        text(f'COMMENT ON COLUMN "{SCHEMA_ECO}"."{TABLE}"."{COL}" IS :comment'),
        {"comment": COL_COMMENT},
    )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        return
    if column_utils.table_has_column(conn, SCHEMA_ECO, TABLE, COL):
        op.drop_column(TABLE, COL, schema=SCHEMA_ECO)
