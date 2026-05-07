"""prospective_place_aes_fields_refactor

Revision ID: x6y7z8a9b0c1
Revises: w5x6y7z8a9b0
Create Date: 2026-03-20

- station_block_number: Integer -> String(100) в machine_prospective_place_aes
- Удаление relative_planned_outage_duration из machine_prospective_place_aes
- Перенос selection_factor из machine_prospective_place_aes в station_prospective_place_aes
"""
from alembic import op
import sqlalchemy as sa


revision = "x6y7z8a9b0c1"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_MACHINE = "machine_prospective_place_aes"
TABLE_STATION = "station_prospective_place_aes"


def upgrade():
    # 1. Добавить selection_factor в station_prospective_place_aes
    op.add_column(
        TABLE_STATION,
        sa.Column("selection_factor", sa.String(length=255), nullable=True),
        schema=SCHEMA_GEN,
    )

    # 2. Скопировать selection_factor из machine в station (первое непустое значение по электростанции)
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE_STATION} s
        SET selection_factor = (
            SELECT m.selection_factor
            FROM {SCHEMA_GEN}.{TABLE_MACHINE} m
            WHERE m.id_station_prospective_place_aes = s.id
              AND m.selection_factor IS NOT NULL
              AND m.selection_factor != ''
            ORDER BY m.id
            LIMIT 1
        )
        """
    )

    # 3. Удалить selection_factor из machine_prospective_place_aes
    op.drop_column(TABLE_MACHINE, "selection_factor", schema=SCHEMA_GEN)

    # 4. Удалить relative_planned_outage_duration из machine_prospective_place_aes
    op.drop_column(TABLE_MACHINE, "relative_planned_outage_duration", schema=SCHEMA_GEN)

    # 5. Изменить station_block_number: Integer -> String(100)
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE_MACHINE}
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
    # 1. station_block_number: String(100) -> Integer
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE_MACHINE}
        ALTER COLUMN station_block_number TYPE INTEGER
        USING (
            CASE
                WHEN station_block_number IS NULL THEN NULL
                WHEN station_block_number ~ '^[0-9]+$' THEN station_block_number::integer
                ELSE NULL
            END
        )
        """
    )

    # 2. Добавить relative_planned_outage_duration в machine_prospective_place_aes
    op.add_column(
        TABLE_MACHINE,
        sa.Column("relative_planned_outage_duration", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )

    # 3. Добавить selection_factor в machine_prospective_place_aes
    op.add_column(
        TABLE_MACHINE,
        sa.Column("selection_factor", sa.String(length=255), nullable=True),
        schema=SCHEMA_GEN,
    )

    # 4. Скопировать selection_factor из station в machine (в первый агрегат каждой электростанции)
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE_MACHINE} m
        SET selection_factor = s.selection_factor
        FROM {SCHEMA_GEN}.{TABLE_STATION} s
        WHERE m.id_station_prospective_place_aes = s.id
          AND m.id = (
              SELECT m2.id
              FROM {SCHEMA_GEN}.{TABLE_MACHINE} m2
              WHERE m2.id_station_prospective_place_aes = s.id
              ORDER BY m2.id
              LIMIT 1
          )
        """
    )

    # 5. Удалить selection_factor из station_prospective_place_aes
    op.drop_column(TABLE_STATION, "selection_factor", schema=SCHEMA_GEN)
