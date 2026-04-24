"""add_planned_unit_capacity_mw_to_prospective_place_aes

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-03-19

Добавляет поле planned_unit_capacity_mw (Планируемая единичная мощность энергоблока, МВт)
в таблицу station_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_aes"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("planned_unit_capacity_mw", sa.Numeric(12, 4), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE, "planned_unit_capacity_mw", schema=SCHEMA_GEN)
