"""change_consumption_k_to_numeric

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-03-17

Меняет тип колонки k в gs_fue_equipment_group_specific_fuel_consumption
с Integer на Numeric(10,4) для поддержки дробных значений (1.5, 0.7 и т.п.).
"""
from alembic import op
import sqlalchemy as sa


revision = 'j2k3l4m5n6o7'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_consumption'
COLUMN = 'k'


def upgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=10, scale=4),
        existing_nullable=True,
        schema=SCHEMA,
        postgresql_using='k::numeric(10,4)',
    )


def downgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Numeric(precision=10, scale=4),
        type_=sa.Integer(),
        existing_nullable=True,
        schema=SCHEMA,
        postgresql_using='ROUND(k)::integer',
    )
