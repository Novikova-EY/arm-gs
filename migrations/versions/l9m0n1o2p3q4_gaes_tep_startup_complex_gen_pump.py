# -*- coding: utf-8 -*-
"""gaes_tep_source: пусковой комплекс — отдельно генераторный и насосный режим.

Revision ID: l9m0n1o2p3q4
Revises: k9l0m1n2o3p4
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "l9m0n1o2p3q4"
down_revision = "k9l0m1n2o3p4"
branch_labels = None
depends_on = None

TABLE = "gaes_tep_source_project_indicators"
SCHEMA_GEN = "gs_gen"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("startup_complex_capacity_mw_generator_mode", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("startup_complex_capacity_mw_pump_mode", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE}
        SET startup_complex_capacity_mw_generator_mode = startup_complex_capacity_mw,
            startup_complex_capacity_mw_pump_mode = startup_complex_capacity_mw
        WHERE startup_complex_capacity_mw IS NOT NULL
        """
    )
    op.drop_column(TABLE, "startup_complex_capacity_mw", schema=SCHEMA_GEN)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("startup_complex_capacity_mw", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_GEN}.{TABLE}
        SET startup_complex_capacity_mw = COALESCE(
            startup_complex_capacity_mw_generator_mode,
            startup_complex_capacity_mw_pump_mode
        )
        """
    )
    op.drop_column(TABLE, "startup_complex_capacity_mw_generator_mode", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "startup_complex_capacity_mw_pump_mode", schema=SCHEMA_GEN)
