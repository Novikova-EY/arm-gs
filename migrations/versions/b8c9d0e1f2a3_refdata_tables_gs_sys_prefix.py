# -*- coding: utf-8 -*-
"""Справочники (app/refdata/models): префикс gs_ -> gs_sys_ в именах таблиц

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-24

Переименование таблиц в схеме gs_sys: gs_* -> gs_sys_*.
"""
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

SCHEMA_REFDATA = "gs_sys"

# Порядок: длинные имена первыми (для наглядности; в PostgreSQL RENAME обновляет FK).
_RENAMES = [
    ("gs_regional_district_regional_energy_system", "gs_sys_regional_district_regional_energy_system"),
    ("gs_refdata_entity_years", "gs_sys_refdata_entity_years"),
    ("gs_refdata_entities", "gs_sys_refdata_entities"),
    ("gs_technology_availabilities", "gs_sys_technology_availabilities"),
    ("gs_regional_energy_systems", "gs_sys_regional_energy_systems"),
    ("gs_pgu_tes_machine_types", "gs_sys_pgu_tes_machine_types"),
    ("gs_union_energy_systems", "gs_sys_union_energy_systems"),
    ("gs_regional_districts", "gs_sys_regional_districts"),
    ("gs_synchronous_areas", "gs_sys_synchronous_areas"),
    ("gs_federal_districts", "gs_sys_federal_districts"),
    ("gs_equipment_groups", "gs_sys_equipment_groups"),
    ("gs_energy_system_types", "gs_sys_energy_system_types"),
    ("gs_fuel_categories", "gs_sys_fuel_categories"),
    ("gs_business_units", "gs_sys_business_units"),
    ("gs_year_features", "gs_sys_year_features"),
    ("gs_condition_types", "gs_sys_condition_types"),
    ("gs_machine_types", "gs_sys_machine_types"),
    ("gs_tes_machine_types", "gs_sys_tes_machine_types"),
    ("gs_technology_types", "gs_sys_technology_types"),
    ("gs_station_types", "gs_sys_station_types"),
    ("gs_energy_areas", "gs_sys_energy_areas"),
    ("gs_energy_zones", "gs_sys_energy_zones"),
    ("gs_energy_units", "gs_sys_energy_units"),
    ("gs_fuel_types", "gs_sys_fuel_types"),
    ("gs_departments", "gs_sys_departments"),
    ("gs_companies", "gs_sys_companies"),
    ("gs_tes_types", "gs_sys_tes_types"),
    ("gs_fuels", "gs_sys_fuels"),
    ("gs_year_service", "gs_sys_year_service"),
    ("gs_years", "gs_sys_years"),
]


def upgrade():
    for old, new in _RENAMES:
        op.rename_table(old, new, schema=SCHEMA_REFDATA)


def downgrade():
    for old, new in reversed(_RENAMES):
        op.rename_table(new, old, schema=SCHEMA_REFDATA)
