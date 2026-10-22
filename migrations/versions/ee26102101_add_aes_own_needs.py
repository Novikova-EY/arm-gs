"""Годовые собственные нужды АЭС, млн.кВт·ч.

Revision ID: ee26102101
Revises: ef26102101
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ENERGY_BALANCE

revision = "ee26102101"
down_revision = "ef26102101"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_bem_station_energy_generations",
        sa.Column("own_needs", sa.Numeric(25, 16), nullable=True),
        schema=SCHEMA_ENERGY_BALANCE,
    )


def downgrade():
    op.drop_column(
        "gs_bem_station_energy_generations", "own_needs", schema=SCHEMA_ENERGY_BALANCE
    )
