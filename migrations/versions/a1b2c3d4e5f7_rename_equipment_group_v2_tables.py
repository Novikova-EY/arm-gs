"""rename equipment group v2 tables to remove _v2 suffix

Revision ID: a1b2c3d4e5f7
Revises: 545183af9073
Create Date: 2026-03-05 12:00:00.000000

Переименовывает таблицы:
- gs_fue_equipment_groups_v2 -> gs_fue_equipment_groups
- gs_fue_equipment_group_sets_v2 -> gs_fue_equipment_group_sets
- gs_fue_equipment_group_type_stations_v2 -> gs_fue_equipment_group_type_stations
"""
from alembic import op
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "545183af9073"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Rename equipment_group_type_stations first (referenced by equipment_group_sets)
    op.rename_table(
        "gs_fue_equipment_group_type_stations_v2",
        "gs_fue_equipment_group_type_stations",
        schema=SCHEMA_FUEL,
    )
    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.gs_fue_equipment_group_type_stations '
        'RENAME CONSTRAINT uq_eq_group_type_station_version_v2 TO uq_eq_group_type_station_version'
    )

    # 2. Rename equipment_groups
    op.rename_table(
        "gs_fue_equipment_groups_v2",
        "gs_fue_equipment_groups",
        schema=SCHEMA_FUEL,
    )

    # 3. Rename equipment_group_sets (references both renamed tables)
    op.rename_table(
        "gs_fue_equipment_group_sets_v2",
        "gs_fue_equipment_group_sets",
        schema=SCHEMA_FUEL,
    )
    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.gs_fue_equipment_group_sets '
        'RENAME CONSTRAINT uq_equipment_group_set_link_v2 TO uq_equipment_group_set_link'
    )


def downgrade():
    # Reverse order
    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.gs_fue_equipment_group_sets '
        'RENAME CONSTRAINT uq_equipment_group_set_link TO uq_equipment_group_set_link_v2'
    )
    op.rename_table(
        "gs_fue_equipment_group_sets",
        "gs_fue_equipment_group_sets_v2",
        schema=SCHEMA_FUEL,
    )

    op.rename_table(
        "gs_fue_equipment_groups",
        "gs_fue_equipment_groups_v2",
        schema=SCHEMA_FUEL,
    )

    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.gs_fue_equipment_group_type_stations '
        'RENAME CONSTRAINT uq_eq_group_type_station_version TO uq_eq_group_type_station_version_v2'
    )
    op.rename_table(
        "gs_fue_equipment_group_type_stations",
        "gs_fue_equipment_group_type_stations_v2",
        schema=SCHEMA_FUEL,
    )
