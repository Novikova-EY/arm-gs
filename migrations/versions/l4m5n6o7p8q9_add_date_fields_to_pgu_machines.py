"""add_date_commission_year_date_exploitation_expected_to_pgu_machines

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-03-18

Добавляет в pgu_machines поля date_commission_year и date_exploitation_expected
для соответствия machine_model (фактический год ввода в работу, ожидаемый год ввода в эксплуатацию).
"""
from alembic import op
import sqlalchemy as sa


revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "pgu_machines"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("date_commission_year", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column("date_exploitation_expected", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_column(TABLE, "date_commission_year", schema=SCHEMA)
    op.drop_column(TABLE, "date_exploitation_expected", schema=SCHEMA)
