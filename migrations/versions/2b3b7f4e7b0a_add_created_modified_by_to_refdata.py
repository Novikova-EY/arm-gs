"""add created_by/modified_by to refdata tables

Revision ID: 2b3b7f4e7b0a
Revises: 1a209997491c
Create Date: 2025-12-01 00:00:00.000000

Миграция добавляет поля аудита (created_by, modified_by) во все
основные справочники схемы refdata, соответствующие моделям,
которые теперь наследуют AuditMixin.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "2b3b7f4e7b0a"
down_revision = "1a209997491c"
branch_labels = None
depends_on = None


def _add_audit_columns(table_name: str) -> None:
    """Добавить created_by / modified_by в указанную таблицу схемы refdata."""
    op.add_column(
        table_name,
        sa.Column("created_by", sa.String(length=255), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        table_name,
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def _drop_audit_columns(table_name: str) -> None:
    """Удалить created_by / modified_by из указанной таблицы схемы refdata."""
    op.drop_column(table_name, "modified_by", schema=SCHEMA_REFDATA)
    op.drop_column(table_name, "created_by", schema=SCHEMA_REFDATA)


def upgrade():
    # Справочники территорий
    _add_audit_columns("federal_districts")
    _add_audit_columns("regional_districts")

    # Энергосистемы
    _add_audit_columns("energy_system_types")
    _add_audit_columns("union_energy_systems")
    _add_audit_columns("regional_energy_systems")
    _add_audit_columns("synchronous_areas")
    _add_audit_columns("energy_zones")
    _add_audit_columns("energy_areas")
    _add_audit_columns("energy_units")

    # Прочие справочники для станций / агрегатов
    _add_audit_columns("condition_types")
    _add_audit_columns("station_types")
    _add_audit_columns("technology_types")
    _add_audit_columns("technology_availabilities")
    _add_audit_columns("equipment_groups")
    _add_audit_columns("machine_types")
    _add_audit_columns("tes_types")
    _add_audit_columns("tes_machine_types")
    _add_audit_columns("pgu_tes_machine_types")

    # Топлива
    _add_audit_columns("fuel_categories")
    _add_audit_columns("fuel_types")
    _add_audit_columns("fuels")

    # Генерирующие компании
    _add_audit_columns("gen_companies")

    # Годы и признаки года
    _add_audit_columns("year_features")
    _add_audit_columns("years")


def downgrade():
    # Откат в обратном порядке, чтобы не мешать возможным зависимостям

    # Годы
    _drop_audit_columns("years")
    _drop_audit_columns("year_features")

    # Генерирующие компании
    _drop_audit_columns("gen_companies")

    # Топлива
    _drop_audit_columns("fuels")
    _drop_audit_columns("fuel_types")
    _drop_audit_columns("fuel_categories")

    # Прочие справочники для станций / агрегатов
    _drop_audit_columns("pgu_tes_machine_types")
    _drop_audit_columns("tes_machine_types")
    _drop_audit_columns("tes_types")
    _drop_audit_columns("machine_types")
    _drop_audit_columns("equipment_groups")
    _drop_audit_columns("technology_availabilities")
    _drop_audit_columns("technology_types")
    _drop_audit_columns("station_types")
    _drop_audit_columns("condition_types")

    # Энергосистемы
    _drop_audit_columns("energy_units")
    _drop_audit_columns("energy_areas")
    _drop_audit_columns("energy_zones")
    _drop_audit_columns("synchronous_areas")
    _drop_audit_columns("regional_energy_systems")
    _drop_audit_columns("union_energy_systems")
    _drop_audit_columns("energy_system_types")

    # Территории
    _drop_audit_columns("regional_districts")
    _drop_audit_columns("federal_districts")


