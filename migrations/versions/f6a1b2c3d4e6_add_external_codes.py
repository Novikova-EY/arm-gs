"""add external_code to stations, equipment groups, machines

Revision ID: f6a1b2c3d4e6
Revises: c7d8e9f0a1b2
Create Date: 2026-01-16 12:00:00.000000

Добавляет внешний стабильный код для станций, групп оборудования и агрегатов.
Трехсторонняя привязка: станция - группа оборудования - агрегат.
"""

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "f6a1b2c3d4e6"
down_revision = "c7d8e9f0a1b2"
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
    op.add_column(
        "stations",
        sa.Column("external_code", sa.String(36), nullable=True),
        schema=SCHEMA_GENERATION,
    )
    op.add_column(
        "machines",
        sa.Column("external_code", sa.String(36), nullable=True),
        schema=SCHEMA_GENERATION,
    )
    op.add_column(
        "gs_equipment_groups",
        sa.Column("external_code", sa.String(36), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        "station_equipment_groups",
        sa.Column("external_code", sa.String(36), nullable=True),
        schema=SCHEMA_GENERATION,
    )

    conn = op.get_bind()

    equipment_rows = conn.execute(
        text(
            f"""
            SELECT id, name
            FROM {SCHEMA_REFDATA}.gs_equipment_groups
            WHERE external_code IS NULL
            """
        )
    ).fetchall()
    for row in equipment_rows:
        code = _stable_uuid(f"equipment_group|{row.name or ''}")
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_REFDATA}.gs_equipment_groups
                SET external_code = :code
                WHERE id = :id
                """
            ),
            {"code": code, "id": row.id},
        )

    station_rows = conn.execute(
        text(
            f"""
            SELECT id, name, name_so, name_combined, id_regional_district
            FROM {SCHEMA_GENERATION}.stations
            WHERE external_code IS NULL
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

    # Заполняем external_code для station_equipment_groups ПЕРЕД machines
    # (чтобы machines могли использовать external_code связок)
    seg_rows = conn.execute(
        text(
            f"""
            SELECT
                seg.id,
                seg.id_station,
                seg.id_equipment_group,
                s.external_code as station_code,
                eg.external_code as equipment_group_code
            FROM {SCHEMA_GENERATION}.station_equipment_groups seg
            LEFT JOIN {SCHEMA_GENERATION}.stations s ON s.id = seg.id_station
            LEFT JOIN {SCHEMA_REFDATA}.gs_equipment_groups eg ON eg.id = seg.id_equipment_group
            WHERE seg.external_code IS NULL
            """
        )
    ).fetchall()
    for row in seg_rows:
        # Используем external_code станции и группы оборудования
        # Если external_code ещё не заполнены (маловероятно), используем ID как fallback
        station_code = row.station_code or f"station_id_{row.id_station}"
        eq_group_code = row.equipment_group_code or f"eq_group_id_{row.id_equipment_group}"
        key = f"station_equipment_group|station|{station_code}|equipment_group|{eq_group_code}"
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

    # Заполняем external_code для machines с трехсторонней привязкой:
    # станция - группа оборудования - агрегат
    machine_rows = conn.execute(
        text(
            f"""
            SELECT
                m.id,
                m.machine_number,
                m.machine_name,
                m.id_ti,
                m.station_equipment_group_id,
                seg.external_code as station_equipment_group_code,
                s.external_code as station_code,
                eg.external_code as equipment_group_code
            FROM {SCHEMA_GENERATION}.machines m
            LEFT JOIN {SCHEMA_GENERATION}.station_equipment_groups seg ON seg.id = m.station_equipment_group_id
            LEFT JOIN {SCHEMA_GENERATION}.stations s ON s.id = m.id_station
            LEFT JOIN {SCHEMA_REFDATA}.gs_equipment_groups eg ON eg.id = m.id_equipment_group
            WHERE m.external_code IS NULL
            """
        )
    ).fetchall()
    for row in machine_rows:
        # Используем external_code связки станция-группа оборудования, если он есть
        station_equipment_group_code = row.station_equipment_group_code
        
        # Если связки нет, формируем её код из станции и группы оборудования
        if not station_equipment_group_code:
            station_code = row.station_code or f"station_id_{row.id}"
            eq_group_code = row.equipment_group_code or f"eq_group_id_{row.id}"
            seg_key = f"station_equipment_group|station|{station_code}|equipment_group|{eq_group_code}"
            station_equipment_group_code = _stable_uuid(seg_key)
        
        # Формируем ключ для трехсторонней привязки: станция-группа оборудования-агрегат
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

    for table_name, schema_name in [
        ("stations", SCHEMA_GENERATION),
        ("machines", SCHEMA_GENERATION),
        ("gs_equipment_groups", SCHEMA_REFDATA),
        ("station_equipment_groups", SCHEMA_GENERATION),
    ]:
        null_rows = conn.execute(
            text(
                f"""
                SELECT id
                FROM {schema_name}.{table_name}
                WHERE external_code IS NULL
                """
            )
        ).fetchall()
        for row in null_rows:
            conn.execute(
                text(
                    f"""
                    UPDATE {schema_name}.{table_name}
                    SET external_code = :code
                    WHERE id = :id
                    """
                ),
                {"code": str(uuid.uuid4()), "id": row.id},
            )

    op.alter_column(
        "stations",
        "external_code",
        nullable=False,
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "machines",
        "external_code",
        nullable=False,
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "gs_equipment_groups",
        "external_code",
        nullable=False,
        schema=SCHEMA_REFDATA,
    )
    op.alter_column(
        "station_equipment_groups",
        "external_code",
        nullable=False,
        schema=SCHEMA_GENERATION,
    )

    op.create_index(
        "ix_station_external_code",
        "stations",
        ["external_code"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )
    op.create_index(
        "ix_machine_external_code",
        "machines",
        ["external_code"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )
    op.create_index(
        "ix_equipment_group_external_code",
        "gs_equipment_groups",
        ["external_code"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        "ix_station_equipment_group_external_code",
        "station_equipment_groups",
        ["external_code"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )


def downgrade():
    op.drop_index(
        "ix_station_external_code",
        table_name="stations",
        schema=SCHEMA_GENERATION,
    )
    op.drop_index(
        "ix_machine_external_code",
        table_name="machines",
        schema=SCHEMA_GENERATION,
    )
    op.drop_index(
        "ix_equipment_group_external_code",
        table_name="gs_equipment_groups",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        "ix_station_equipment_group_external_code",
        table_name="station_equipment_groups",
        schema=SCHEMA_GENERATION,
    )

    op.drop_column("stations", "external_code", schema=SCHEMA_GENERATION)
    op.drop_column("machines", "external_code", schema=SCHEMA_GENERATION)
    op.drop_column("gs_equipment_groups", "external_code", schema=SCHEMA_REFDATA)
    op.drop_column("station_equipment_groups", "external_code", schema=SCHEMA_GENERATION)
