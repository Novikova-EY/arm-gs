# -*- coding: utf-8 -*-
"""Переименование peak_datetime_msk -> peak_datetime в таблицах нагрузок (gs_pd).

Revision ID: a9c8b7d6e5f4
Revises: z7a8b9c0d1e2
Create Date: 2026-08-20
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS_DIR not in sys.path:
    sys.path.insert(0, _MIGRATIONS_DIR)
import column_utils  # noqa: E402

revision = "a9c8b7d6e5f4"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
OLD_COLUMN = "peak_datetime_msk"
NEW_COLUMN = "peak_datetime"

_TABLES = (
    "gs_pd_centralized_zone_demand_params",
    "gs_pd_ees_demand_params",
    "gs_pd_ees_russia_demand_params",
    "gs_pd_energy_area_demand_params",
    "gs_pd_energy_system_type_demand_params",
    "gs_pd_energy_unit_demand_params",
    "gs_pd_energy_zone_demand_params",
    "gs_pd_federal_district_demand_params",
    "gs_pd_regional_district_demand_params",
    "gs_pd_regional_energy_system_demand_params",
    "gs_pd_russia_federation_demand_params",
    "gs_pd_synchronous_area_demand_params",
    "gs_pd_union_energy_system_demand_params",
)


def _rename_column(conn, table: str, old_name: str, new_name: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA_PD, table):
        return
    if not column_utils.table_has_column(conn, SCHEMA_PD, table, old_name):
        return
    if column_utils.table_has_column(conn, SCHEMA_PD, table, new_name):
        return
    op.execute(
        text(
            f'ALTER TABLE "{SCHEMA_PD}"."{table}" '
            f'RENAME COLUMN "{old_name}" TO "{new_name}"'
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        _rename_column(conn, table, OLD_COLUMN, NEW_COLUMN)


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        _rename_column(conn, table, NEW_COLUMN, OLD_COLUMN)
