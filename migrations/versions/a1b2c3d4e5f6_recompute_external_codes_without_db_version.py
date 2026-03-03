"""recompute external_code without db_version for equipment_group_sets and machines

Revision ID: b2c3d4e5f6a8
Revises: 2602c2c7c150
Create Date: 2026-02-19 00:00:00.000000

Исправляет external_code: один и тот же агрегат/станция-группа в разных версиях БД
должен иметь одинаковый external_code. Ранее в ключ EquipmentGroupSet входил db_version,
что давало разные коды в разных версиях. Теперь db_version исключён из ключа.
"""

import uuid
from alembic import op
from sqlalchemy.sql import text
from config import SCHEMA_FUEL, SCHEMA_GENERATION


revision = "b2c3d4e5f6a8"
down_revision = "2602c2c7c150"
branch_labels = None
depends_on = None


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def upgrade():
    conn = op.get_bind()

    # 1. Пересчёт external_code для equipment_group_sets (БЕЗ db_version)
    sets_table = f"{SCHEMA_FUEL}.gs_fue_equipment_group_sets"
    sets_rows = conn.execute(
        text(
            f"""
            SELECT id, id_equipment_group, name
            FROM {sets_table}
            """
        )
    ).fetchall()

    for row in sets_rows:
        row_id, equipment_group_id, name = row
        safe_name = name or f"equipment_group_set_id_{row_id}"
        eg_id = equipment_group_id or 0
        key = f"equipment_group_set|name|{safe_name}|equipment_group_id|{eg_id}"
        code = _stable_uuid(key)
        conn.execute(
            text(f"UPDATE {sets_table} SET external_code = :code WHERE id = :id"),
            {"code": code, "id": row_id},
        )

    # 2. Пересчёт external_code для machines (зависит от equipment_group_set)
    machines_table = f"{SCHEMA_GENERATION}.machines"
    machine_rows = conn.execute(
        text(
            f"""
            SELECT
                m.id,
                m.id_station,
                m.id_equipment_group,
                m.machine_number,
                m.machine_name,
                m.id_ti,
                egs.external_code AS equipment_group_set_code,
                s.external_code AS station_code
            FROM {machines_table} m
            LEFT JOIN {SCHEMA_FUEL}.gs_fue_equipment_group_sets egs
                ON egs.id = m.equipment_group_set_id
            LEFT JOIN {SCHEMA_GENERATION}.stations s
                ON s.id = m.id_station
            """
        )
    ).fetchall()

    for row in machine_rows:
        if row.equipment_group_set_code:
            eg_set_code = row.equipment_group_set_code
        else:
            station_code = row.station_code or f"station_id_{row.id_station}"
            equipment_group_id = row.id_equipment_group or 0
            seg_key = (
                f"station_equipment_group|station|{station_code}|"
                f"equipment_group_id|{equipment_group_id}"
            )
            eg_set_code = _stable_uuid(seg_key)

        machine_key = (
            f"machine|equipment_group_set|{eg_set_code}|"
            f"ti|{row.id_ti or ''}|num|{row.machine_number or ''}|name|{row.machine_name or ''}"
        )
        code = _stable_uuid(machine_key)
        conn.execute(
            text(f"UPDATE {machines_table} SET external_code = :code WHERE id = :id"),
            {"code": code, "id": row.id},
        )


def downgrade():
    # Откат не выполняется: предыдущие external_code не восстановить.
    pass
