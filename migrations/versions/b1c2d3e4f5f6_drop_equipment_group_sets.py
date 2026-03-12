"""drop equipment group sets

Revision ID: b1c2d3e4f5f6
Revises: a8b9c0d1e2f3
Create Date: 2026-03-05 00:00:00.000000

Удаляет таблицы gs_fue_equipment_group_sets и gs_fue_equipment_group_set_stations,
а также колонку machines.equipment_group_set_id и связанные ограничения.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL, SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5f6"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    # Убираем FK на gs_fue_equipment_group_set_stations (если есть)
    if inspector.has_table("gs_fue_equipment_group_fuel_param", schema=SCHEMA_FUEL):
        fks = inspector.get_foreign_keys(
            "gs_fue_equipment_group_fuel_param", schema=SCHEMA_FUEL
        )
        for fk in fks:
            if "equipment_group_set_station_id" in (fk.get("constrained_columns") or []):
                if fk.get("name"):
                    op.drop_constraint(
                        fk["name"],
                        "gs_fue_equipment_group_fuel_param",
                        schema=SCHEMA_FUEL,
                        type_="foreignkey",
                    )

    # Убираем FK на gs_fue_equipment_group_sets (если есть)
    if inspector.has_table("gs_fue_equipment_group_extra_fuel_param", schema=SCHEMA_FUEL):
        fks = inspector.get_foreign_keys(
            "gs_fue_equipment_group_extra_fuel_param", schema=SCHEMA_FUEL
        )
        for fk in fks:
            if "id_equipment_group_set" in (fk.get("constrained_columns") or []):
                if fk.get("name"):
                    op.drop_constraint(
                        fk["name"],
                        "gs_fue_equipment_group_extra_fuel_param",
                        schema=SCHEMA_FUEL,
                        type_="foreignkey",
                    )

    # Убираем ссылку из machines
    if inspector.has_table("machines", schema=SCHEMA_GENERATION):
        op.execute(
            f"DROP INDEX IF EXISTS {SCHEMA_GENERATION}.ix_machine_equipment_group_set_id"
        )
        op.execute(
            f"ALTER TABLE {SCHEMA_GENERATION}.machines "
            "DROP CONSTRAINT IF EXISTS fk_machines_equipment_group_set_id"
        )
        machine_columns = {
            col["name"] for col in inspector.get_columns("machines", schema=SCHEMA_GENERATION)
        }
        if "equipment_group_set_id" in machine_columns:
            op.drop_column("machines", "equipment_group_set_id", schema=SCHEMA_GENERATION)

    # Удаляем таблицы связей и групп оборудования
    if inspector.has_table("gs_fue_equipment_group_set_stations", schema=SCHEMA_FUEL):
        op.drop_table("gs_fue_equipment_group_set_stations", schema=SCHEMA_FUEL)
    if inspector.has_table("gs_fue_equipment_group_sets", schema=SCHEMA_FUEL):
        op.drop_table("gs_fue_equipment_group_sets", schema=SCHEMA_FUEL)


def downgrade():
    # Осознанно не восстанавливаем удаленные таблицы и колонку.
    pass
