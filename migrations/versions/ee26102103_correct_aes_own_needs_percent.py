"""СН, % АЭС = СН, млн.кВт·ч / выработка * 100.

Revision ID: ee26102103
Revises: ee26102102
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ENERGY_BALANCE

revision = "ee26102103"
down_revision = "ee26102102"
branch_labels = None
depends_on = None


def _recalculate(*, reverse=False):
    table = sa.table(
        "gs_bem_station_energy_generations",
        sa.column("month_number", sa.Integer),
        sa.column("own_needs", sa.Numeric),
        sa.column("electricity_generation", sa.Numeric),
        sa.column("own_needs_percent", sa.Numeric),
        schema=SCHEMA_ENERGY_BALANCE,
    )
    numerator, denominator = table.c.own_needs, table.c.electricity_generation
    if reverse:
        numerator, denominator = denominator, numerator
    op.execute(
        table.update()
        .where(table.c.month_number == 0, table.c.own_needs.is_not(None))
        .values(own_needs_percent=numerator / sa.func.nullif(denominator, 0) * 100)
    )


def upgrade():
    _recalculate()


def downgrade():
    _recalculate(reverse=True)
