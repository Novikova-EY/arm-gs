# -*- coding: utf-8 -*-
"""Удалить устаревшие unique-индексы gs_pd_union_energy_system_demand_params без perimeter_variant_code.

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-06-24
"""
from alembic import op
from sqlalchemy import text

revision = "v1w2x3y4z5a6"
down_revision = "u0v1w2x3y4z5"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_union_energy_system_demand_params"
FK_COL = "id_union_energy_system"

_LEGACY_INDEXES = (
    "uq_ues_demand_params_hist",
    "uq_ues_demand_params_year",
    "uq_ues_dp_hist",
    "uq_ues_dp_year",
    "uq_gs_union_energy_system_demand_params_hist",
    "uq_gs_union_energy_system_demand_params_year",
    "uq_gs_pd_union_energy_system_demand_params_hist",
    "uq_gs_pd_union_energy_system_demand_params_year",
)


def upgrade():
    conn = op.get_bind()
    for ix in _LEGACY_INDEXES:
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_union_energy_system_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_union_energy_system_demand_params_year
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
        "uq_gs_pd_union_energy_system_demand_params_hist",
        "uq_gs_pd_union_energy_system_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ues_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ues_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )
