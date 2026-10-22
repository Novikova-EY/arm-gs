"""Хранение расчётного или введённого вручную СН, % АЭС.

Revision ID: ee26102102
Revises: ee26102101
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ENERGY_BALANCE

revision = "ee26102102"
down_revision = "ee26102101"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_bem_station_energy_generations",
        sa.Column("own_needs_percent", sa.Numeric(36, 16), nullable=True),
        schema=SCHEMA_ENERGY_BALANCE,
    )
    table = sa.table(
        "gs_bem_station_energy_generations",
        sa.column("month_number", sa.Integer),
        sa.column("own_needs", sa.Numeric),
        sa.column("electricity_generation", sa.Numeric),
        sa.column("own_needs_percent", sa.Numeric),
        schema=SCHEMA_ENERGY_BALANCE,
    )
    op.execute(
        table.update()
        .where(table.c.month_number == 0, table.c.own_needs.is_not(None))
        .values(own_needs_percent=table.c.electricity_generation / sa.func.nullif(table.c.own_needs, 0) * 100)
    )


def downgrade():
    op.drop_column(
        "gs_bem_station_energy_generations", "own_needs_percent", schema=SCHEMA_ENERGY_BALANCE
    )
