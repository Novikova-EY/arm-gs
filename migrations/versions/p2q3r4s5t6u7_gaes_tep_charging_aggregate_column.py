# -*- coding: utf-8 -*-
"""gaes_tep_source: годовое потребление на заряд без разбивки по очередям.

Revision ID: p2q3r4s5t6u7
Revises: n5o6p7q8r9s0
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "p2q3r4s5t6u7"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None

TABLE = "gaes_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("annual_charging_electricity_consumption_million_kwh", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE, "annual_charging_electricity_consumption_million_kwh", schema=SCHEMA_GEN)
