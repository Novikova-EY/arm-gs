# -*- coding: utf-8 -*-
"""Столбцы combined_on_fo, combined_on_cz_russia в gs_pd_regional_energy_system_demand_params.

Revision ID: b0c1d2e3f4a5
Revises: z3a4b5c6d7e8
Create Date: 2026-05-12

Совмещенное потребление мощности на час прохождения максимума ФО, МВт; Совмещенное потребление мощности на час прохождения максимума ЦЗ России, МВт.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "b0c1d2e3f4a5"
down_revision = "z3a4b5c6d7e8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE_RES = "gs_pd_regional_energy_system_demand_params"
COL_TYPE = sa.Numeric(precision=25, scale=16)

NEW_COLS = ("combined_on_fo", "combined_on_cz_russia")


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
    for col_name in NEW_COLS:
        if _column_exists(conn, SCHEMA_PD, TABLE_RES, col_name):
            continue
        op.add_column(
            TABLE_RES,
            sa.Column(col_name, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for col_name in reversed(tuple(NEW_COLS)):
        if not _column_exists(conn, SCHEMA_PD, TABLE_RES, col_name):
            continue
        op.drop_column(TABLE_RES, col_name, schema=SCHEMA_PD)
