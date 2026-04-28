# -*- coding: utf-8 -*-
"""gs_pd.gs_pd_union_energy_system_demand_params: расчетный максимум и расч. совм. макс. на ЕЭС.

Revision ID: u1v2w3x4y5z6
Revises: m9n0o1p2q3r4
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "u1v2w3x4y5z6"
down_revision = "m9n0o1p2q3r4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_union_energy_system_demand_params"
COL_TYPE = sa.Numeric(precision=25, scale=16)

COLUMNS = ("calculated_max_power_mw", "calculated_combined_on_ees_mw")


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
    for col_name in COLUMNS:
        if _column_exists(conn, SCHEMA_PD, TABLE, col_name):
            continue
        op.add_column(
            TABLE,
            sa.Column(col_name, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for col_name in reversed(COLUMNS):
        if not _column_exists(conn, SCHEMA_PD, TABLE, col_name):
            continue
        op.drop_column(TABLE, col_name, schema=SCHEMA_PD)
