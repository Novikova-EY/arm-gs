"""rename equipment_group_toplivo_param to equipment_group_fuel_param

Revision ID: z9a0b1c2d3e4
Revises: y8z9a0b1c2d3
Create Date: 2026-02-26

Переименовывает таблицу gs_fue_equipment_group_toplivo_param
в gs_fue_equipment_group_fuel_param.
"""

from alembic import op
from config import SCHEMA_FUEL


revision = "z9a0b1c2d3e4"
down_revision = "y8z9a0b1c2d3"
branch_labels = None
depends_on = None

OLD_TABLE = "gs_fue_equipment_group_toplivo_param"
NEW_TABLE = "gs_fue_equipment_group_fuel_param"
SCHEMA = SCHEMA_FUEL


def upgrade():
    op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)


def downgrade():
    op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)
