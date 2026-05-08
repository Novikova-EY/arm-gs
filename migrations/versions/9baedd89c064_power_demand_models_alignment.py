# -*- coding: utf-8 -*-
"""gs_pd: add combined_on_cz (FO, subject), combined_on_fo (subject), combined_on_ez (RES).

Revision ID: 9baedd89c064
Revises: t3u4v5w6x7y8
Create Date: 2026-04-10
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


revision = "9baedd89c064"
down_revision = "t3u4v5w6x7y8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
COL_TYPE = sa.Numeric(precision=25, scale=16)

_ADD_COLUMNS_LEGACY = (
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
    for legacy, col in _ADD_COLUMNS_LEGACY:
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            continue
        if _column_exists(conn, SCHEMA_PD, physical, col):
            continue
        op.add_column(
            physical,
            sa.Column(col, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for legacy, col in reversed(_ADD_COLUMNS_LEGACY):
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            continue
        if not _column_exists(conn, SCHEMA_PD, physical, col):
            continue
        op.drop_column(physical, col, schema=SCHEMA_PD)
