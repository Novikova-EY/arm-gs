# -*- coding: utf-8 -*-
"""gaes_tep_source: единичная мощность агрегата — генераторный и насосный режим.

Revision ID: n5o6p7q8r9s0
Revises: l9m0n1o2p3q4
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "n5o6p7q8r9s0"
down_revision = "l9m0n1o2p3q4"
branch_labels = None
depends_on = None

TABLE = "gaes_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("unit_capacity_mw_generator_mode", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("unit_capacity_mw_pump_mode", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE}
        SET unit_capacity_mw_generator_mode = unit_capacity_mw,
            unit_capacity_mw_pump_mode = unit_capacity_mw
        WHERE unit_capacity_mw IS NOT NULL
        """
    )
    op.drop_column(TABLE, "unit_capacity_mw", schema=SCHEMA_GEN)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("unit_capacity_mw", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE}
        SET unit_capacity_mw = COALESCE(
            unit_capacity_mw_generator_mode,
            unit_capacity_mw_pump_mode
        )
        """
    )
    op.drop_column(TABLE, "unit_capacity_mw_generator_mode", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "unit_capacity_mw_pump_mode", schema=SCHEMA_GEN)
