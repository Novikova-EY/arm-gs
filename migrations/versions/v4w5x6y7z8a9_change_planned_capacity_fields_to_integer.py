"""change_planned_capacity_fields_to_integer

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
Create Date: 2026-03-19

Меняет типы полей planned_capacity_mw и planned_unit_capacity_mw на Integer
в таблице station_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_aes"


def upgrade():
    # planned_capacity_mw: String -> Integer (пустые и нечисловые значения -> NULL)
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE}
        ALTER COLUMN planned_capacity_mw TYPE INTEGER
        USING (
            CASE
                WHEN planned_capacity_mw IS NULL OR TRIM(planned_capacity_mw) = '' THEN NULL
                WHEN planned_capacity_mw ~ '^\\s*-?[0-9]+\\s*$' THEN TRIM(planned_capacity_mw)::integer
                ELSE NULL
            END
        )
        """
    )
    # planned_unit_capacity_mw: Numeric -> Integer
    op.execute(
        f"""
        ALTER TABLE {SCHEMA_GEN}.{TABLE}
        ALTER COLUMN planned_unit_capacity_mw TYPE INTEGER
        USING planned_unit_capacity_mw::integer
        """
    )


def downgrade():
    op.alter_column(
        TABLE,
        "planned_capacity_mw",
        type_=sa.String(100),
        schema=SCHEMA_GEN,
        postgresql_using="planned_capacity_mw::text",
    )
    op.alter_column(
        TABLE,
        "planned_unit_capacity_mw",
        type_=sa.Numeric(12, 4),
        schema=SCHEMA_GEN,
        postgresql_using="planned_unit_capacity_mw::numeric(12,4)",
    )
