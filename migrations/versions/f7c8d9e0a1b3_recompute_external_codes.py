"""recompute external_code with updated rules

Revision ID: f7c8d9e0a1b3
Revises: a9d1c2b3e4f5
Create Date: 2026-01-19 12:00:00.000000

Пересчитывает external_code для станций, связок станция-группа оборудования и агрегатов
по актуальным правилам.
"""

import uuid
from alembic import op
from sqlalchemy.sql import text
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "f7c8d9e0a1b3"
down_revision = "a9d1c2b3e4f5"
branch_labels = None
depends_on = None


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def _station_key(name, name_so, name_combined, district_id):
    if name_so:
        return f"station|so|{name_so}"
    if name_combined:
        return f"station|combined|{name_combined}"
    return f"station|name|{name or ''}|district|{district_id or ''}"


def upgrade():
    conn = op.get_bind()

    station_rows = conn.execute(
        text(
            f"""
            SELECT id, name, name_so, name_combined, id_regional_district
            FROM {SCHEMA_GENERATION}.stations
            """
        )
    ).fetchall()
    for row in station_rows:
        key = _station_key(row.name, row.name_so, row.name_combined, row.id_regional_district)
        code = _stable_uuid(key)
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_GENERATION}.stations
                SET external_code = :code
                WHERE id = :id
                """
            ),
            {"code": code, "id": row.id},
        )

    seg_rows = conn.execute(
        text(
            f"""
            SELECT
                seg.id,
                seg.id_station,
                seg.id_equipment_group,
                s.external_code as station_code
            FROM {SCHEMA_GENERATION}.station_equipment_groups seg
            LEFT JOIN {SCHEMA_GENERATION}.stations s ON s.id = seg.id_station
            """
        )
    ).fetchall()
    for row in seg_rows:
        station_code = row.station_code or f"station_id_{row.id_station}"
        equipment_group_id = row.id_equipment_group or 0
        key = f"station_equipment_group|station|{station_code}|equipment_group_id|{equipment_group_id}"
        code = _stable_uuid(key)
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_GENERATION}.station_equipment_groups
                SET external_code = :code
                WHERE id = :id
                """
            ),
            {"code": code, "id": row.id},
        )

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
                seg.external_code as station_equipment_group_code,
                s.external_code as station_code
            FROM {SCHEMA_GENERATION}.machines m
            LEFT JOIN {SCHEMA_GENERATION}.station_equipment_groups seg ON seg.id = m.station_equipment_group_id
            LEFT JOIN {SCHEMA_GENERATION}.stations s ON s.id = m.id_station
            """
        )
    ).fetchall()
    for row in machine_rows:
        station_equipment_group_code = row.station_equipment_group_code
        if not station_equipment_group_code:
            station_code = row.station_code or f"station_id_{row.id_station}"
            equipment_group_id = row.id_equipment_group or 0
            seg_key = (
                f"station_equipment_group|station|{station_code}|equipment_group_id|{equipment_group_id}"
            )
            station_equipment_group_code = _stable_uuid(seg_key)

        machine_key = (
            f"machine|station_equipment_group|{station_equipment_group_code}|"
            f"ti|{row.id_ti or ''}|num|{row.machine_number or ''}|name|{row.machine_name or ''}"
        )
        code = _stable_uuid(machine_key)
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_GENERATION}.machines
                SET external_code = :code
                WHERE id = :id
                """
            ),
            {"code": code, "id": row.id},
        )


def downgrade():
    # Данные были пересчитаны детерминированно; откат не выполняется.
    pass
