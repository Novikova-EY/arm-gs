"""possible_implementation_period_to_string

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
Create Date: 2026-03-20

Изменяет тип поля possible_implementation_period с Integer на String(50)
для поддержки форматов: 2042 или 31.12.2042
"""
from alembic import op


revision = "y7z8a9b0c1d2"
down_revision = "x6y7z8a9b0c1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "machine_prospective_place_aes"


def upgrade():
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE}
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
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE}
        ALTER COLUMN possible_implementation_period TYPE INTEGER
        USING (
            CASE
                WHEN possible_implementation_period IS NULL THEN NULL
                WHEN possible_implementation_period ~ '^[0-9]+$' THEN possible_implementation_period::integer
                ELSE NULL
            END
        )
        """
    )
