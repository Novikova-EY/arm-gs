# -*- coding: utf-8 -*-
"""Колонка note (примечание) во всех таблицах параметров нагрузки gs_pd *_demand_params.

Revision ID: f7e8d9c0b1a2
Revises: 49b16675688d
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "f7e8d9c0b1a2"
down_revision = "49b16675688d"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"

TABLES = (
    "gs_pd_centralized_zone_demand_params",
    "gs_pd_ees_demand_params",
    "gs_pd_ees_russia_demand_params",
    "gs_pd_ees_russia_with_nt_demand_params",
    "gs_pd_energy_area_demand_params",
    "gs_pd_energy_system_type_demand_params",
    "gs_pd_energy_unit_demand_params",
    "gs_pd_energy_zone_demand_params",
    "gs_pd_federal_district_demand_params",
    "gs_pd_regional_district_demand_params",
    "gs_pd_regional_energy_system_demand_params",
    "gs_pd_russia_federation_demand_params",
    "gs_pd_russia_federation_with_nt_demand_params",
    "gs_pd_synchronous_area_demand_params",
    "gs_pd_union_energy_system_demand_params",
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
    for table in TABLES:
        if _column_exists(conn, SCHEMA_PD, table, "note"):
            continue
        op.add_column(
            table,
            sa.Column("note", sa.Text(), nullable=True),
            schema=SCHEMA_PD,
        )


def downgrade():
    conn = op.get_bind()
    for table in reversed(TABLES):
        if not _column_exists(conn, SCHEMA_PD, table, "note"):
            continue
        op.drop_column(table, "note", schema=SCHEMA_PD)
