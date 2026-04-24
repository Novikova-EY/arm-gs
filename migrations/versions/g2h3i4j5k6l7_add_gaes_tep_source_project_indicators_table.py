# -*- coding: utf-8 -*-
"""add_gaes_tep_source_project_indicators_table

Revision ID: g2h3i4j5k6l7
Revises: f1e2d3c4b5a6
Create Date: 2026-03-31

Таблица перечня исходных ТЭП ГАЭС (ProspectivePlaceGaesTepSource).
Ранее миграции только добавляли колонки (e7f8a9b0c1d2), сама таблица не создавалась.
"""
from alembic import op
import sqlalchemy as sa


revision = "g2h3i4j5k6l7"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"

TABLE_TEP = "gaes_tep_source_project_indicators"
TABLE_STATION = "station_prospective_place_gaes"
TABLE_TYPES = "gs_prospective_place_types_gaes"


def _has_table(bind, schema: str, table: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return table in insp.get_table_names(schema=schema)
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, SCHEMA_GEN, TABLE_TEP):
        return

    op.create_table(
        TABLE_TEP,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_station_prospective_place_gaes", sa.Integer(), nullable=False),
        sa.Column("id_prospective_place_type_gaes", sa.Integer(), nullable=True),
        sa.Column("installed_capacity_mw_generator_mode", sa.String(length=100), nullable=True),
        sa.Column("stage_1_capacity_mw_generator_mode", sa.String(length=100), nullable=True),
        sa.Column("stage_2_capacity_mw_generator_mode", sa.String(length=100), nullable=True),
        sa.Column("installed_capacity_mw_pump_mode", sa.String(length=100), nullable=True),
        sa.Column("stage_1_capacity_mw_pump_mode", sa.String(length=100), nullable=True),
        sa.Column("stage_2_capacity_mw_pump_mode", sa.String(length=100), nullable=True),
        sa.Column("startup_complex_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("units_count", sa.Integer(), nullable=True),
        sa.Column("unit_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("hydro_turbine_type", sa.String(length=500), nullable=True),
        sa.Column("ccium_turbine_mode", sa.String(length=100), nullable=True),
        sa.Column("ccium_pump_mode", sa.String(length=100), nullable=True),
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        sa.Column("construction_increment_year_01_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_02_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_03_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_04_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_05_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_06_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_07_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_08_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_09_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_10_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_11_mw", sa.String(length=100), nullable=True),
        sa.Column("specific_semifixed_operating_costs_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("generation_average_multiyear_billion_kwh", sa.String(length=100), nullable=True),
        sa.Column("generation_average_multiyear_million_kwh_stage_1", sa.String(length=100), nullable=True),
        sa.Column("generation_average_multiyear_million_kwh_stage_2", sa.String(length=100), nullable=True),
        sa.Column("generation_medium_water_50pct_billion_kwh", sa.String(length=100), nullable=True),
        sa.Column("generation_low_water_95pct_billion_kwh", sa.String(length=100), nullable=True),
        sa.Column("annual_charging_electricity_consumption_million_kwh_stage_1", sa.String(length=100), nullable=True),
        sa.Column("annual_charging_electricity_consumption_million_kwh_stage_2", sa.String(length=100), nullable=True),
        sa.Column("specific_capital_investment_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("capital_investment_gaes_construction_current_prices_billion_rub", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_gaes_tep_source_id_station",
        TABLE_TEP,
        ["id_station_prospective_place_gaes"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_gaes_tep_source_id_prospective_place_type_gaes",
        TABLE_TEP,
        ["id_prospective_place_type_gaes"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_gaes_tep_source_project_indicators_database_version_id",
        TABLE_TEP,
        ["database_version_id"],
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_gaes_tep_station_prospective_place_gaes",
        TABLE_TEP,
        TABLE_STATION,
        ["id_station_prospective_place_gaes"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_GEN,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_gaes_tep_prospective_place_type_gaes",
        TABLE_TEP,
        TABLE_TYPES,
        ["id_prospective_place_type_gaes"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_gaes_tep_database_version",
        TABLE_TEP,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, SCHEMA_GEN, TABLE_TEP):
        return
    op.drop_table(TABLE_TEP, schema=SCHEMA_GEN)
