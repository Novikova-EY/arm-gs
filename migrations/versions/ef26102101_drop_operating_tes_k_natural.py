"""Удаление коэффициента K из характеристик топлива действующих ТЭС.

Revision ID: ef26102101
Revises: ef26102003
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY

revision = "ef26102101"
down_revision = "ef26102003"
branch_labels = None
depends_on = None

_TABLE = "gs_eco_operating_tes_fuel_chars"


def upgrade():
    op.drop_column(_TABLE, "k_natural", schema=SCHEMA_ECOLOGY)


def downgrade():
    op.add_column(
        _TABLE,
        sa.Column("k_natural", sa.Numeric(36, 16), nullable=True),
        schema=SCHEMA_ECOLOGY,
    )
