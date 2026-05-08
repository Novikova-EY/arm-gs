"""possible_implementation_period_to_string

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
Create Date: 2026-03-20

Изменяет тип поля possible_implementation_period с Integer на String(50)
для поддержки форматов: 2042 или 31.12.2042
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "y7z8a9b0c1d2"
down_revision = "x6y7z8a9b0c1"
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
        ALTER COLUMN possible_implementation_period TYPE VARCHAR(50)
        USING (
            CASE
                WHEN possible_implementation_period IS NULL THEN NULL
                ELSE possible_implementation_period::text
            END
        )
        """
    )


def downgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{table}
        ALTER COLUMN possible_implementation_period TYPE INTEGER
        USING (
            CASE
                WHEN possible_implementation_period IS NULL THEN NULL
                WHEN possible_implementation_period::text ~ '^\\s*[0-9]+\\s*$'
                    THEN TRIM(possible_implementation_period::text)::integer
                ELSE NULL
            END
        )
        """
    )
