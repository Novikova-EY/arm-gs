# -*- coding: utf-8 -*-
"""Удалить устаревшие unique-индексы gs_pd_synchronous_area_demand_params без perimeter_variant_code.

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-06-24
"""
from alembic import op
from sqlalchemy import text

revision = "u0v1w2x3y4z5"
down_revision = "t9u0v1w2x3y4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_synchronous_area_demand_params"
FK_COL = "id_synchronous_area"

_LEGACY_INDEXES = (
    "uq_sa_demand_params_hist",
    "uq_sa_demand_params_year",
    "uq_sa_dp_hist",
    "uq_sa_dp_year",
    "uq_gs_synchronous_area_demand_params_hist",
    "uq_gs_synchronous_area_demand_params_year",
)


def upgrade():
    conn = op.get_bind()
    for ix in _LEGACY_INDEXES:
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_synchronous_area_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_synchronous_area_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    for ix in (
        "uq_gs_pd_synchronous_area_demand_params_hist",
        "uq_gs_pd_synchronous_area_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_sa_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_sa_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )
