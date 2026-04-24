# -*- coding: utf-8 -*-
"""Таблицы параметров нагрузки (demand) для EnergyArea, FederalDistrict, EnergyUnit, EnergyZone,
RegionalDistrict, SynchronousArea, UnionEnergySystem, EnergySystemType.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


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


def _table_exists(connection, schema: str, table: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def _create_demand_params_table(
    table: str,
    fk_col: str,
    ref_table: str,
    ix_suffix: str,
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
            [f"{SCHEMA_REFDATA}.{ref_table}.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_PD,
    )
    op.create_index(
        f"ix_{table}_{fk_col}",
        table,
        [fk_col],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.create_index(
        f"ix_{table}_year_number",
        table,
        ["year_number"],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.create_index(
        f"ix_{table}_database_version_id",
        table,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_{ix_suffix}_demand_params_hist
            ON "{SCHEMA_PD}"."{table}" (
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
            CREATE UNIQUE INDEX uq_{ix_suffix}_demand_params_year
            ON "{SCHEMA_PD}"."{table}" (
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
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    for table, fk_col, ref_table, ix_suffix in _DEMAND_PARAM_TABLES:
        if _table_exists(conn, SCHEMA_PD, table):
            continue
        _create_demand_params_table(table, fk_col, ref_table, ix_suffix)


def downgrade():
    conn = op.get_bind()
    for table, _, _, _ in reversed(_DEMAND_PARAM_TABLES):
        if _table_exists(conn, SCHEMA_PD, table):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{table}" CASCADE'))
