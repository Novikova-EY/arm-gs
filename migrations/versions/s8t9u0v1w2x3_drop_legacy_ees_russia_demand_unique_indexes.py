# -*- coding: utf-8 -*-
"""Удалить устаревшие unique-индексы gs_pd_ees_russia_demand_params без perimeter_variant_code.

Revision ID: s8t9u0v1w2x3
Revises: r7s8t9u0v1w2
Create Date: 2026-06-22
"""
from alembic import op
from sqlalchemy import text

revision = "s8t9u0v1w2x3"
down_revision = "r7s8t9u0v1w2"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
_LEGACY_INDEXES = ("uq_ees_russia_dp_hist", "uq_ees_russia_dp_year")


def upgrade():
    conn = op.get_bind()
    for ix in _LEGACY_INDEXES:
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ees_russia_dp_hist
            ON "{SCHEMA_PD}"."gs_pd_ees_russia_demand_params" (
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ees_russia_dp_year
            ON "{SCHEMA_PD}"."gs_pd_ees_russia_demand_params" (
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )
