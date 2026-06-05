# -*- coding: utf-8 -*-
"""Электроёмкость: parameter_value Numeric(25, 16) -> Numeric(25, 10).

Revision ID: d4e5f6a7b8c2
Revises: c3d4e5f6a7b0
Create Date: 2026-06-04
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

revision = "d4e5f6a7b8c2"
down_revision = "c3d4e5f6a7b0"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
OLD_TYPE = sa.Numeric(precision=25, scale=16)
NEW_TYPE = sa.Numeric(precision=25, scale=10)
FRACTION_DIGITS = 10

TABLES = (
    "gs_ec_federal_district_electrical_intensity_year_params",
    "gs_ec_russia_federation_electrical_intensity_year_params",
)
COLUMN = "parameter_value"
INTENSITY_ROW_KINDS = ("intensity", "calculated", "delta")


def _table_exists(conn, table: str) -> bool:
    return column_utils.table_exists(conn, SCHEMA_EC, table)


def _round_intensity_values(conn, table: str) -> None:
    kinds_sql = ", ".join(f"'{k}'" for k in INTENSITY_ROW_KINDS)
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_EC}.{table}
            SET {COLUMN} = ROUND({COLUMN}::numeric, :digits)
            WHERE {COLUMN} IS NOT NULL
              AND row_kind IN ({kinds_sql})
            """
        ),
        {"digits": FRACTION_DIGITS},
    )


def _alter_parameter_value(conn, table: str, *, reverse: bool) -> None:
    if not _table_exists(conn, table):
        return
    if reverse:
        op.alter_column(
            table,
            COLUMN,
            existing_type=NEW_TYPE,
            type_=OLD_TYPE,
            existing_nullable=True,
            schema=SCHEMA_EC,
            postgresql_using=f"{COLUMN}::numeric",
        )
        return
    _round_intensity_values(conn, table)
    op.alter_column(
        table,
        COLUMN,
        existing_type=OLD_TYPE,
        type_=NEW_TYPE,
        existing_nullable=True,
        schema=SCHEMA_EC,
        postgresql_using=f"ROUND({COLUMN}::numeric, {FRACTION_DIGITS})",
    )


def upgrade():
    conn = op.get_bind()
    for table in TABLES:
        _alter_parameter_value(conn, table, reverse=False)


def downgrade():
    conn = op.get_bind()
    for table in reversed(TABLES):
        _alter_parameter_value(conn, table, reverse=True)
