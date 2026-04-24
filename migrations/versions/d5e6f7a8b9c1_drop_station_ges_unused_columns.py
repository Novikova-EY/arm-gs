"""drop_station_ges_unused_columns

Revision ID: d5e6f7a8b9c1
Revises: c4d5e6f7a8b0
Create Date: 2026-03-30

Удаление неиспользуемых полей из station_prospective_place_ges.
"""
from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c1"
down_revision = "c4d5e6f7a8b0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_ges"

COLS = (
    "regional_subject_name",
    "planned_unit_capacity_mw",
    "selection_factor",
    "construction_period_years_minenergo_protocol",
)


def upgrade():
    for col in COLS:
        op.drop_column(TABLE, col, schema=SCHEMA_GEN)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("regional_subject_name", sa.String(length=255), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("planned_unit_capacity_mw", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("selection_factor", sa.Text(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("construction_period_years_minenergo_protocol", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
