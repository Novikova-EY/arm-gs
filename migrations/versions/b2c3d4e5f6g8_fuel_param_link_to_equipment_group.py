"""fuel param: equipment_group_set_station_id/id_equipment_group_set -> equipment_group_id

Revision ID: b2c3d4e5f6g8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-05 14:00:00.000000

Меняет связь в EquipmentGroupFuelParam и EquipmentGroupExtraFuelParam
на EquipmentGroup вместо EquipmentGroupSetStation/EquipmentGroupSet.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUEL


revision = "b2c3d4e5f6g8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

FUEL_PARAM_TABLE = "gs_fue_equipment_group_fuel_param"


def _drop_fuel_param_old_unique(conn):
    """Удаляет старые unique indexes и constraints на equipment_group_set_station_id."""
    inspector = inspect(conn)
    to_drop_idx = [
        idx["name"]
        for idx in inspector.get_indexes(FUEL_PARAM_TABLE, schema=SCHEMA_FUEL)
        if idx.get("unique") and "equipment_group_set_station_id" in (idx.get("column_names") or [])
    ]
    to_drop_uq = [
        uq["name"]
        for uq in inspector.get_unique_constraints(FUEL_PARAM_TABLE, schema=SCHEMA_FUEL)
        if "equipment_group_set_station_id" in (uq.get("column_names") or [])
    ]
    for name in to_drop_idx:
        op.drop_index(name, table_name=FUEL_PARAM_TABLE, schema=SCHEMA_FUEL)
    for name in to_drop_uq:
        op.drop_constraint(name, FUEL_PARAM_TABLE, schema=SCHEMA_FUEL, type_="unique")


def upgrade():
    conn = op.get_bind()

    # --- EquipmentGroupFuelParam ---
    op.add_column(
        FUEL_PARAM_TABLE,
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{FUEL_PARAM_TABLE} fp
        SET equipment_group_id = (
            SELECT egs.equipment_group_id
            FROM {SCHEMA_FUEL}.gs_fue_equipment_group_sets egs
            WHERE egs.equipment_group_set_station_id = fp.equipment_group_set_station_id
            LIMIT 1
        )
        WHERE fp.equipment_group_set_station_id IS NOT NULL
        """
    )
    _drop_fuel_param_old_unique(conn)
    # Удаляем строки, которые не удалось сопоставить (equipment_group_id IS NULL)
    op.execute(
        f"DELETE FROM {SCHEMA_FUEL}.{FUEL_PARAM_TABLE} WHERE equipment_group_id IS NULL"
    )
    # Удаляем старую колонку
    op.drop_column(
        FUEL_PARAM_TABLE,
        "equipment_group_set_station_id",
        schema=SCHEMA_FUEL,
    )
    # Делаем equipment_group_id NOT NULL
    op.alter_column(
        FUEL_PARAM_TABLE,
        "equipment_group_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA_FUEL,
    )
    # Добавляем FK и unique constraint
    op.create_foreign_key(
        "fk_equipment_group_fuel_param_equipment_group",
        "gs_fue_equipment_group_fuel_param",
        "gs_fue_equipment_groups",
        ["equipment_group_id"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_FUEL,
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_equipment_group_fuel_param_group_year",
        "gs_fue_equipment_group_fuel_param",
        ["equipment_group_id", "year_number"],
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_equipment_group_fuel_param_equipment_group_id",
        "gs_fue_equipment_group_fuel_param",
        ["equipment_group_id"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

    # --- EquipmentGroupExtraFuelParam ---
    op.add_column(
        "gs_fue_equipment_group_extra_fuel_param",
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    # Мигрируем данные: id_equipment_group_set -> equipment_group_id через numb1120 -> EquipmentGroup.numb
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.gs_fue_equipment_group_extra_fuel_param efp
        SET equipment_group_id = (
            SELECT eg.id
            FROM {SCHEMA_FUEL}.gs_fue_equipment_groups eg
            WHERE eg.numb IS NOT NULL
              AND TRIM(eg.numb) = efp.numb1120::text
            LIMIT 1
        )
        WHERE efp.numb1120 IS NOT NULL
        """
    )
    op.drop_constraint(
        "uq_equipment_group_extra_fuel_param_set_year",
        "gs_fue_equipment_group_extra_fuel_param",
        schema=SCHEMA_FUEL,
        type_="unique",
    )
    op.drop_index(
        "ix_eg_extra_fuel_param_eg_set",
        table_name="gs_fue_equipment_group_extra_fuel_param",
        schema=SCHEMA_FUEL,
    )
    op.drop_column(
        "gs_fue_equipment_group_extra_fuel_param",
        "id_equipment_group_set",
        schema=SCHEMA_FUEL,
    )
    op.create_foreign_key(
        "fk_equipment_group_extra_fuel_param_equipment_group",
        "gs_fue_equipment_group_extra_fuel_param",
        "gs_fue_equipment_groups",
        ["equipment_group_id"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_FUEL,
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_equipment_group_extra_fuel_param_group_year",
        "gs_fue_equipment_group_extra_fuel_param",
        ["equipment_group_id", "year_number"],
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_equipment_group_extra_fuel_param_equipment_group_id",
        "gs_fue_equipment_group_extra_fuel_param",
        ["equipment_group_id"],
        unique=False,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    # Reverse order
    op.drop_constraint(
        "uq_equipment_group_extra_fuel_param_group_year",
        "gs_fue_equipment_group_extra_fuel_param",
        schema=SCHEMA_FUEL,
        type_="unique",
    )
    op.drop_constraint(
        "fk_equipment_group_extra_fuel_param_equipment_group",
        "gs_fue_equipment_group_extra_fuel_param",
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_equipment_group_extra_fuel_param_equipment_group_id",
        table_name="gs_fue_equipment_group_extra_fuel_param",
        schema=SCHEMA_FUEL,
    )
    op.add_column(
        "gs_fue_equipment_group_extra_fuel_param",
        sa.Column("id_equipment_group_set", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.create_unique_constraint(
        "uq_equipment_group_extra_fuel_param_set_year",
        "gs_fue_equipment_group_extra_fuel_param",
        ["id_equipment_group_set", "year_number"],
        schema=SCHEMA_FUEL,
    )
    op.drop_column(
        "gs_fue_equipment_group_extra_fuel_param",
        "equipment_group_id",
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_eg_extra_fuel_param_eg_set",
        "gs_fue_equipment_group_extra_fuel_param",
        ["id_equipment_group_set"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

    op.drop_constraint(
        "uq_equipment_group_fuel_param_group_year",
        "gs_fue_equipment_group_fuel_param",
        schema=SCHEMA_FUEL,
        type_="unique",
    )
    op.drop_constraint(
        "fk_equipment_group_fuel_param_equipment_group",
        "gs_fue_equipment_group_fuel_param",
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_equipment_group_fuel_param_equipment_group_id",
        table_name="gs_fue_equipment_group_fuel_param",
        schema=SCHEMA_FUEL,
    )
    op.add_column(
        "gs_fue_equipment_group_fuel_param",
        sa.Column("equipment_group_set_station_id", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.create_unique_constraint(
        "uq_equipment_group_fuel_param_station_year",
        "gs_fue_equipment_group_fuel_param",
        ["equipment_group_set_station_id", "year_number"],
        schema=SCHEMA_FUEL,
    )
    op.drop_column(
        "gs_fue_equipment_group_fuel_param",
        "equipment_group_id",
        schema=SCHEMA_FUEL,
    )
