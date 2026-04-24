"""remove_service_life_construction_commissioning_from_prospective_place_aes

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-03-19

Удаляет поля service_life_years, construction_period_years, commissioning_year
из таблицы station_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_aes"


def upgrade():
    op.drop_column(TABLE, "service_life_years", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "construction_period_years", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "commissioning_year", schema=SCHEMA_GEN)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("service_life_years", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("commissioning_year", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
