# -*- coding: utf-8 -*-
"""ges_tep_source_project_indicators: прирост мощности за 12-й год.

Revision ID: x9a0b1c2d3e4
Revises: w6x7y8z9a0b1
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "x9a0b1c2d3e4"
down_revision = "w6x7y8z9a0b1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "ges_tep_source_project_indicators"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("construction_increment_year_12_mw", sa.String(length=100), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE, "construction_increment_year_12_mw", schema=SCHEMA_GEN)
