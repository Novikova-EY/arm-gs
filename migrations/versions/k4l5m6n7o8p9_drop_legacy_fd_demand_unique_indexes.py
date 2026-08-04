# -*- coding: utf-8 -*-
"""Удалить устаревшие unique-индексы gs_pd_federal_district_demand_params без perimeter_variant_code.

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-07-31
"""
from alembic import op
from sqlalchemy import text

revision = "k4l5m6n7o8p9"
down_revision = "j3k4l5m6n7o8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_federal_district_demand_params"
FK_COL = "id_federal_district"

_LEGACY_INDEXES = (
    "uq_fd_demand_params_hist",
    "uq_fd_demand_params_year",
    "uq_federal_district_demand_params_hist",
    "uq_federal_district_demand_params_year",
)


def upgrade():
    conn = op.get_bind()
    for ix in _LEGACY_INDEXES:
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_federal_district_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_federal_district_demand_params_year
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
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_fd_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_fd_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )
