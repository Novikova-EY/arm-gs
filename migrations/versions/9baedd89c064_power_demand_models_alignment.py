# -*- coding: utf-8 -*-
"""gs_pd: add combined_on_cz (FO, subject), combined_on_fo (subject), combined_on_ez (RES).

Revision ID: 9baedd89c064
Revises: t3u4v5w6x7y8
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "9baedd89c064"
down_revision = "t3u4v5w6x7y8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
COL_TYPE = sa.Numeric(precision=25, scale=16)

# (table, column)
_ADD_COLUMNS = (
    ("gs_federal_district_demand_params", "combined_on_cz"),
    ("gs_regional_district_demand_params", "combined_on_fo"),
    ("gs_regional_district_demand_params", "combined_on_cz"),
    ("gs_regional_energy_system_demand_params", "combined_on_ez"),
)


def _column_exists(connection, schema: str, table: str, column: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    for table, column in _ADD_COLUMNS:
        if _column_exists(conn, SCHEMA_PD, table, column):
            continue
        op.add_column(
            table,
            sa.Column(column, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for table, column in reversed(_ADD_COLUMNS):
        if not _column_exists(conn, SCHEMA_PD, table, column):
            continue
        op.drop_column(table, column, schema=SCHEMA_PD)
