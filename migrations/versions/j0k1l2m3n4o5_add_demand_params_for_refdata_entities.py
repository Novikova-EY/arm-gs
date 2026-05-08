# -*- coding: utf-8 -*-
"""Таблицы параметров нагрузки (demand) для EnergyArea, FederalDistrict, EnergyUnit, EnergyZone,
RegionalDistrict, SynchronousArea, UnionEnergySystem, EnergySystemType.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-09
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


revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"

# (table_name, fk_column, referenced_table, suffix for unique index names)
_DEMAND_PARAM_TABLES = (
    ("gs_energy_area_demand_params", "id_energy_area", "gs_energy_areas", "ea"),
    ("gs_federal_district_demand_params", "id_federal_district", "gs_federal_districts", "fd"),
    ("gs_energy_unit_demand_params", "id_energy_unit", "gs_energy_units", "eu"),
    ("gs_energy_zone_demand_params", "id_energy_zone", "gs_energy_zones", "ez"),
    ("gs_regional_district_demand_params", "id_regional_district", "gs_regional_districts", "rd"),
    ("gs_synchronous_area_demand_params", "id_synchronous_area", "gs_synchronous_areas", "sa"),
    ("gs_union_energy_system_demand_params", "id_union_energy_system", "gs_union_energy_systems", "ues"),
    ("gs_energy_system_type_demand_params", "id_energy_system_type", "gs_energy_system_types", "est"),
)


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _create_demand_params_table(
    table: str,
    fk_col: str,
    ref_versions: str,
    resolved_ref_table: str,
) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(fk_col, sa.Integer(), nullable=False),
        sa.Column("is_historical_maximum", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("max_power_consumption_mw", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("peak_datetime_msk", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_daily_air_temp_c", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("combined_on_oes", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("combined_on_ees", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name=f"ck_{table}_year_vs_hist",
        ),
        sa.ForeignKeyConstraint(
            [fk_col],
            [f"{SCHEMA_REFDATA}.{resolved_ref_table}.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_PD,
    )


def _ensure_demand_params_indexes(
    conn, physical_table: str, index_name_table: str, fk_col: str, ix_suffix: str
) -> None:
    ix_fk = f"ix_{index_name_table}_{fk_col}"
    if not column_utils.index_exists(conn, SCHEMA_PD, ix_fk):
        op.create_index(ix_fk, physical_table, [fk_col], unique=False, schema=SCHEMA_PD)
    ix_year = f"ix_{index_name_table}_year_number"
    if not column_utils.index_exists(conn, SCHEMA_PD, ix_year):
        op.create_index(ix_year, physical_table, ["year_number"], unique=False, schema=SCHEMA_PD)
    ix_dbver = f"ix_{index_name_table}_database_version_id"
    if not column_utils.index_exists(conn, SCHEMA_PD, ix_dbver):
        op.create_index(ix_dbver, physical_table, ["database_version_id"], unique=False, schema=SCHEMA_PD)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_hist
            ON "{SCHEMA_PD}"."{physical_table}" (
                {fk_col},
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_year
            ON "{SCHEMA_PD}"."{physical_table}" (
                {fk_col},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    for legacy, fk_col, ref_table, ix_suffix in _DEMAND_PARAM_TABLES:
        resolved_ref_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, ref_table)
        if resolved_ref_table is None:
            return
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            _create_demand_params_table(legacy, fk_col, ref_versions, resolved_ref_table)
            physical = legacy
        _ensure_demand_params_indexes(conn, physical, legacy, fk_col, ix_suffix)


def downgrade():
    conn = op.get_bind()
    for legacy, _, _, _ in reversed(_DEMAND_PARAM_TABLES):
        pd_tbl = "gs_pd_" + legacy[len("gs_") :]
        for tbl in (pd_tbl, legacy):
            if column_utils.table_exists(conn, SCHEMA_PD, tbl):
                op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{tbl}" CASCADE'))
