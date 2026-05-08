"""prospective_place_aes_fields_refactor

Revision ID: x6y7z8a9b0c1
Revises: w5x6y7z8a9b0
Create Date: 2026-03-20

- station_block_number: Integer -> String(100) в machine_prospective_place_aes
- Удаление relative_planned_outage_duration из machine_prospective_place_aes
- Перенос selection_factor из machine_prospective_place_aes в station_prospective_place_aes
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "x6y7z8a9b0c1"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_MACHINE = "machine_prospective_place_aes"
TABLE_STATION = "station_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table_machine = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_station = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table_machine is None or table_station is None:
        return
    # 1. Добавить selection_factor в station_prospective_place_aes
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_station, "selection_factor"):
        op.add_column(
            table_station,
            sa.Column("selection_factor", sa.String(length=255), nullable=True),
            schema=SCHEMA_GEN,
        )

    # 2. Скопировать selection_factor из machine в station только если колонка еще есть в machine.
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "selection_factor"):
        op.execute(
            f"""
            UPDATE {SCHEMA_GEN}.{table_station} s
            SET selection_factor = (
                SELECT m.selection_factor
                FROM {SCHEMA_GEN}.{table_machine} m
                WHERE m.id_station_prospective_place_aes = s.id
                  AND m.selection_factor IS NOT NULL
                  AND m.selection_factor != ''
                ORDER BY m.id
                LIMIT 1
            )
            """
        )

    # 3. Удалить selection_factor из machine_prospective_place_aes
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "selection_factor"):
        op.drop_column(table_machine, "selection_factor", schema=SCHEMA_GEN)

    # 4. Удалить relative_planned_outage_duration из machine_prospective_place_aes
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "relative_planned_outage_duration"):
        op.drop_column(table_machine, "relative_planned_outage_duration", schema=SCHEMA_GEN)

    # 5. Изменить station_block_number: Integer -> String(100)
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{table_machine}
        ALTER COLUMN station_block_number TYPE VARCHAR(100)
        USING (
            CASE
                WHEN station_block_number IS NULL THEN NULL
                ELSE station_block_number::text
            END
        )
        """
    )


def downgrade():
    conn = op.get_bind()
    table_machine = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_station = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table_machine is None or table_station is None:
        return
    # 1. station_block_number: String(100) -> Integer
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{table_machine}
        ALTER COLUMN station_block_number TYPE INTEGER
        USING (
            CASE
                WHEN station_block_number IS NULL THEN NULL
                WHEN station_block_number::text ~ '^\\s*[0-9]+\\s*$' THEN TRIM(station_block_number::text)::integer
                ELSE NULL
            END
        )
        """
    )

    # 2. Добавить relative_planned_outage_duration в machine_prospective_place_aes
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "relative_planned_outage_duration"):
        op.add_column(
            table_machine,
            sa.Column("relative_planned_outage_duration", sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )

    # 3. Добавить selection_factor в machine_prospective_place_aes
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "selection_factor"):
        op.add_column(
            table_machine,
            sa.Column("selection_factor", sa.String(length=255), nullable=True),
            schema=SCHEMA_GEN,
        )

    # 4. Скопировать selection_factor из station в machine только если колонка есть в station.
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_station, "selection_factor"):
        op.execute(
            f"""
            UPDATE {SCHEMA_GEN}.{table_machine} m
            SET selection_factor = s.selection_factor
            FROM {SCHEMA_GEN}.{table_station} s
            WHERE m.id_station_prospective_place_aes = s.id
              AND m.id = (
                  SELECT m2.id
                  FROM {SCHEMA_GEN}.{table_machine} m2
                  WHERE m2.id_station_prospective_place_aes = s.id
                  ORDER BY m2.id
                  LIMIT 1
              )
            """
        )

    # 5. Удалить selection_factor из station_prospective_place_aes
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_station, "selection_factor"):
        op.drop_column(table_station, "selection_factor", schema=SCHEMA_GEN)
