"""rename Fuel and FuelType topl_nazvl, topl_kmbur to short names

Revision ID: c2d3e4f5a6b7
Revises: a0b1c2d3e4f5
Create Date: 2026-02-26

Переименовывает в gs_fuels: topl_nazvl->nazvl, topl_kmbur->kmbur.
Переименовывает в gs_fuel_types: topl_nazvl->nazvl.
"""

from alembic import op
from config import SCHEMA_REFDATA


revision = "c2d3e4f5a6b7"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None

SCHEMA = SCHEMA_REFDATA


def upgrade():
    op.alter_column("gs_fuels", "topl_nazvl", new_column_name="nazvl", schema=SCHEMA)
    op.alter_column("gs_fuels", "topl_kmbur", new_column_name="kmbur", schema=SCHEMA)
    op.alter_column("gs_fuel_types", "topl_nazvl", new_column_name="nazvl", schema=SCHEMA)


def downgrade():
    op.alter_column("gs_fuels", "nazvl", new_column_name="topl_nazvl", schema=SCHEMA)
    op.alter_column("gs_fuels", "kmbur", new_column_name="topl_kmbur", schema=SCHEMA)
    op.alter_column("gs_fuel_types", "nazvl", new_column_name="topl_nazvl", schema=SCHEMA)
