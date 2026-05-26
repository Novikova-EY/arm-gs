# -*- coding: utf-8 -*-
"""Переименование combined_on_cz_russia -> combined_on_cz (РЭС, gs_pd).

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE_RES = "gs_pd_regional_energy_system_demand_params"


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
    if _column_exists(conn, SCHEMA_PD, TABLE_RES, "combined_on_cz_russia") and not _column_exists(
        conn, SCHEMA_PD, TABLE_RES, "combined_on_cz"
    ):
        op.alter_column(
            TABLE_RES,
            "combined_on_cz_russia",
            new_column_name="combined_on_cz",
            existing_type=sa.Numeric(25, 16),
            nullable=True,
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, SCHEMA_PD, TABLE_RES, "combined_on_cz") and not _column_exists(
        conn, SCHEMA_PD, TABLE_RES, "combined_on_cz_russia"
    ):
        op.alter_column(
            TABLE_RES,
            "combined_on_cz",
            new_column_name="combined_on_cz_russia",
            existing_type=sa.Numeric(25, 16),
            nullable=True,
            schema=SCHEMA_PD,
        )
