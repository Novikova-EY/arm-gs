"""Allow NULL station_id for standalone equipment group links.

Revision ID: b6c7d8e9f0a1
Revises: a4b5c6d7e8f9
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "b6c7d8e9f0a1"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
TABLE = "gs_fue_equipment_group_type_stations"
COLUMN = "station_id"


def upgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA_FUEL,
    )
