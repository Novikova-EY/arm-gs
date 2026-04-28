# -*- coding: utf-8 -*-
"""Хранение коэффициентов k (ручной среднесрочный) в параметрах РЭС и ОЭС.

Revision ID: a8b9c0d1e2f3
Revises: u1v2w3x4y5z6
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "a8b9c0d1e2f3"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE_RES = "gs_pd_regional_energy_system_demand_params"
TABLE_UES = "gs_pd_union_energy_system_demand_params"
COL_TYPE = sa.Numeric(precision=25, scale=16)

RES_COLS = ("coeff_k_combined_on_oes", "coeff_k_combined_on_ees")
UES_COLS = (
    "coeff_k_calculated_max_power_mw",
    "coeff_k_combined_on_ees",
    "coeff_k_calculated_combined_on_ees_mw",
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
    for col_name in RES_COLS:
        if _column_exists(conn, SCHEMA_PD, TABLE_RES, col_name):
            continue
        op.add_column(
            TABLE_RES,
            sa.Column(col_name, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )
    for col_name in UES_COLS:
        if _column_exists(conn, SCHEMA_PD, TABLE_UES, col_name):
            continue
        op.add_column(
            TABLE_UES,
            sa.Column(col_name, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for col_name in reversed(tuple(UES_COLS)):
        if not _column_exists(conn, SCHEMA_PD, TABLE_UES, col_name):
            continue
        op.drop_column(TABLE_UES, col_name, schema=SCHEMA_PD)
    for col_name in reversed(tuple(RES_COLS)):
        if not _column_exists(conn, SCHEMA_PD, TABLE_RES, col_name):
            continue
        op.drop_column(TABLE_RES, col_name, schema=SCHEMA_PD)
