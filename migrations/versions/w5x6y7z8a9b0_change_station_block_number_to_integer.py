"""change_station_block_number_to_integer

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-03-19

Меняет тип поля station_block_number на Integer в таблице machine_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "machine_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{table}
        ALTER COLUMN station_block_number TYPE INTEGER
        USING (
            CASE
                WHEN station_block_number IS NULL THEN NULL
                WHEN station_block_number::text ~ '^\\s*-?[0-9]+(?:[.,][0-9]+)?\\s*$'
                    THEN ROUND(REPLACE(TRIM(station_block_number::text), ',', '.')::numeric)::integer
                ELSE NULL
            END
        )
        """
    )


def downgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    op.alter_column(
        table,
        "station_block_number",
        type_=sa.Numeric(36, 15),
        schema=SCHEMA_GEN,
        postgresql_using="station_block_number::numeric(36,15)",
    )
