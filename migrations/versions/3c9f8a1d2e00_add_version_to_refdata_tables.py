"""add version column to refdata tables for optimistic locking

Revision ID: 3c9f8a1d2e00
Revises: 2b3b7f4e7b0a
Create Date: 2025-12-01 00:10:00.000000

Миграция добавляет колонку `version` во все основные справочные таблицы
схемы refdata, которые теперь наследуют VersionedModelMixin.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "3c9f8a1d2e00"
down_revision = "2b3b7f4e7b0a"
branch_labels = None
depends_on = None


def _add_version_column(table_name: str) -> None:
    """Добавить колонку version в указанную таблицу схемы refdata."""
    op.add_column(
        table_name,
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        schema=SCHEMA_REFDATA,
    )


def _drop_version_column(table_name: str) -> None:
    """Удалить колонку version из указанной таблицы схемы refdata."""
    op.drop_column(table_name, "version", schema=SCHEMA_REFDATA)


def upgrade():
    # Территории
    _add_version_column("federal_districts")
    _add_version_column("regional_districts")

    # Энергосистемы
    _add_version_column("energy_system_types")
    _add_version_column("union_energy_systems")
    _add_version_column("regional_energy_systems")
    _add_version_column("synchronous_areas")
    _add_version_column("energy_zones")
    _add_version_column("energy_areas")
    _add_version_column("energy_units")

    # Прочие справочники для станций / агрегатов
    _add_version_column("condition_types")
    _add_version_column("station_types")
    _add_version_column("technology_types")
    _add_version_column("technology_availabilities")
    _add_version_column("equipment_groups")
    _add_version_column("machine_types")
    _add_version_column("tes_types")
    _add_version_column("tes_machine_types")
    _add_version_column("pgu_tes_machine_types")

    # Топлива
    _add_version_column("fuel_categories")
    _add_version_column("fuel_types")
    _add_version_column("fuels")

    # Генерирующие компании
    _add_version_column("gen_companies")

    # Годы и признаки года
    _add_version_column("year_features")
    _add_version_column("years")


def downgrade():
    # Откат в обратном порядке

    # Годы и признаки года
    _drop_version_column("years")
    _drop_version_column("year_features")

    # Генерирующие компании
    _drop_version_column("gen_companies")

    # Топлива
    _drop_version_column("fuels")
    _drop_version_column("fuel_types")
    _drop_version_column("fuel_categories")

    # Прочие справочники для станций / агрегатов
    _drop_version_column("pgu_tes_machine_types")
    _drop_version_column("tes_machine_types")
    _drop_version_column("tes_types")
    _drop_version_column("machine_types")
    _drop_version_column("equipment_groups")
    _drop_version_column("technology_availabilities")
    _drop_version_column("technology_types")
    _drop_version_column("station_types")
    _drop_version_column("condition_types")

    # Энергосистемы
    _drop_version_column("energy_units")
    _drop_version_column("energy_areas")
    _drop_version_column("energy_zones")
    _drop_version_column("synchronous_areas")
    _drop_version_column("regional_energy_systems")
    _drop_version_column("union_energy_systems")
    _drop_version_column("energy_system_types")

    # Территории
    _drop_version_column("regional_districts")
    _drop_version_column("federal_districts")


