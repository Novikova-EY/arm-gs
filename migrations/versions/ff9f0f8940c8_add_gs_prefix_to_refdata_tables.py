"""add gs_ prefix to refdata tables

Revision ID: ff9f0f8940c8
Revises: 3c9f8a1d2e00
Create Date: 2025-01-27 12:00:00.000000

Миграция переименовывает все таблицы схемы refdata, добавляя префикс gs_
к их названиям. Это необходимо для единообразия именования таблиц.

Перед выполнением миграции необходимо предоставить права на переименование таблиц.
Выполните SQL-скрипт: scripts/grant_permissions_for_table_rename.sql
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "ff9f0f8940c8"
down_revision = "3c9f8a1d2e00"
branch_labels = None
depends_on = None


def _rename_table(old_name: str, new_name: str) -> None:
    """Переименовать таблицу в схеме refdata."""
    op.rename_table(old_name, new_name, schema=SCHEMA_REFDATA)


def upgrade():
    """
    Переименование всех таблиц refdata с добавлением префикса gs_.
    
    Порядок важен: сначала переименовываем таблицы, которые не имеют
    зависимостей или имеют минимальные зависимости, затем остальные.
    """
    
    # 1. Базовая таблица версий (зависимости от других таблиц минимальны)
    _rename_table("database_versions", "gs_database_versions")
    
    # 2. Независимые справочники
    _rename_table("fuel_categories", "gs_fuel_categories")
    _rename_table("fuel_types", "gs_fuel_types")
    _rename_table("fuels", "gs_fuels")
    _rename_table("year_features", "gs_year_features")
    _rename_table("years", "gs_years")
    _rename_table("energy_system_types", "gs_energy_system_types")
    _rename_table("energy_zones", "gs_energy_zones")
    _rename_table("synchronous_areas", "gs_synchronous_areas")
    _rename_table("condition_types", "gs_condition_types")
    _rename_table("station_types", "gs_station_types")
    _rename_table("machine_types", "gs_machine_types")
    _rename_table("tes_types", "gs_tes_types")
    _rename_table("tes_machine_types", "gs_tes_machine_types")
    _rename_table("pgu_tes_machine_types", "gs_pgu_tes_machine_types")
    _rename_table("technology_types", "gs_technology_types")
    _rename_table("technology_availabilities", "gs_technology_availabilities")
    _rename_table("equipment_groups", "gs_equipment_groups")
    _rename_table("gen_companies", "gs_companies")
    
    # Добавление поля name_short в таблицу gs_companies
    op.add_column(
        "gs_companies",
        sa.Column("name_short", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA
    )
    # Создание индекса для поля name_short
    op.create_index(
        op.f('ix_refdata_gs_companies_name_short'),
        'gs_companies',
        ['name_short'],
        unique=False,
        schema=SCHEMA_REFDATA
    )
    
    # 3. Территории (зависит от energy_zones, synchronous_areas)
    _rename_table("federal_districts", "gs_federal_districts")
    _rename_table("regional_districts", "gs_regional_districts")
    
    # 4. Энергосистемы (зависит от regional_districts, energy_system_types)
    _rename_table("union_energy_systems", "gs_union_energy_systems")
    _rename_table("regional_energy_systems", "gs_regional_energy_systems")
    _rename_table("energy_areas", "gs_energy_areas")
    _rename_table("energy_units", "gs_energy_units")
    
    # 5. Ассоциативная таблица (зависит от regional_districts, regional_energy_systems)
    _rename_table("regional_district_regional_energy_system", "gs_regional_district_regional_energy_system")


def downgrade():
    """
    Откат переименования таблиц - удаление префикса gs_.
    
    Порядок обратный upgrade() для сохранения зависимостей.
    """
    
    # 5. Ассоциативная таблица
    _rename_table("gs_regional_district_regional_energy_system", "regional_district_regional_energy_system")
    
    # 4. Энергосистемы
    _rename_table("gs_energy_units", "energy_units")
    _rename_table("gs_energy_areas", "energy_areas")
    _rename_table("gs_regional_energy_systems", "regional_energy_systems")
    _rename_table("gs_union_energy_systems", "union_energy_systems")
    
    # 3. Территории
    _rename_table("gs_regional_districts", "regional_districts")
    _rename_table("gs_federal_districts", "federal_districts")
    
    # 2. Независимые справочники
    # Удаление поля name_short из таблицы gs_companies перед откатом переименования
    op.drop_index(
        op.f('ix_refdata_gs_companies_name_short'),
        table_name='gs_companies',
        schema=SCHEMA_REFDATA
    )
    op.drop_column("gs_companies", "name_short", schema=SCHEMA_REFDATA)
    
    _rename_table("gs_companies", "gen_companies")
    _rename_table("gs_equipment_groups", "equipment_groups")
    _rename_table("gs_technology_availabilities", "technology_availabilities")
    _rename_table("gs_technology_types", "technology_types")
    _rename_table("gs_pgu_tes_machine_types", "pgu_tes_machine_types")
    _rename_table("gs_tes_machine_types", "tes_machine_types")
    _rename_table("gs_tes_types", "tes_types")
    _rename_table("gs_machine_types", "machine_types")
    _rename_table("gs_station_types", "station_types")
    _rename_table("gs_condition_types", "condition_types")
    _rename_table("gs_synchronous_areas", "synchronous_areas")
    _rename_table("gs_energy_zones", "energy_zones")
    _rename_table("gs_energy_system_types", "energy_system_types")
    _rename_table("gs_years", "years")
    _rename_table("gs_year_features", "year_features")
    _rename_table("gs_fuels", "fuels")
    _rename_table("gs_fuel_types", "fuel_types")
    _rename_table("gs_fuel_categories", "fuel_categories")
    
    # 1. Базовая таблица версий
    _rename_table("gs_database_versions", "database_versions")

