# -*- coding: utf-8 -*-
"""Столбец combined_on_es (Совмещенный на ЭС, МВт) в таблицах параметров нагрузки gs_pd.

Revision ID: t3u4v5w6x7y8
Revises: q1r2s3t4u5v6
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


revision = "t3u4v5w6x7y8"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
COLUMN = "combined_on_es"
COL_TYPE = sa.Numeric(precision=25, scale=16)

_DEMAND_PARAM_TABLES_LEGACY = (
    "gs_energy_area_demand_params",
    "gs_ees_demand_params",
    "gs_energy_system_type_demand_params",
    "gs_ees_russia_demand_params",
    "gs_energy_zone_demand_params",
    "gs_federal_district_demand_params",
    "gs_russia_federation_with_nt_demand_params",
    "gs_energy_unit_demand_params",
    "gs_regional_district_demand_params",
    "gs_russia_federation_demand_params",
    "gs_regional_energy_system_demand_params",
    "gs_synchronous_area_demand_params",
    "gs_union_energy_system_demand_params",
    "gs_ees_russia_with_nt_demand_params",
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
    for legacy in _DEMAND_PARAM_TABLES_LEGACY:
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            continue
        if _column_exists(conn, SCHEMA_PD, physical, COLUMN):
            continue
        op.add_column(
            physical,
            sa.Column(COLUMN, COL_TYPE, nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for legacy in reversed(_DEMAND_PARAM_TABLES_LEGACY):
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            continue
        if not _column_exists(conn, SCHEMA_PD, physical, COLUMN):
            continue
        op.drop_column(physical, COLUMN, schema=SCHEMA_PD)
